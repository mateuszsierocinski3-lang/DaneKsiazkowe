import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import xml.etree.ElementTree as ET

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz Pro", page_icon="📖", layout="wide")

# --- MAPOWANIE JĘZYKÓW ---
LANG_MAP = {
    'pol': 'polski', 'eng': 'angielski', 'ger': 'nieznany',
    'fre': 'francuski', 'rus': 'rosyjski', 'ita': 'włoski', 'spa': 'hiszpański'
}

# --- FUNKCJA ODWRACANIA AUTORÓW ---
def reverse_authors(authors_str):
    if not authors_str or authors_str in ["Nieznany", "Brak", "Błąd danych", "Brak ISBN w bazie"]:
        return authors_str
    
    individual_authors = [a.strip() for a in authors_str.split(',')]
    reversed_list = []
    
    for author in individual_authors:
        parts = author.split()
        if len(parts) >= 2:
            last_name = parts[-1]
            first_names = " ".join(parts[:-1])
            reversed_list.append(f"{last_name} {first_names}")
        else:
            reversed_list.append(author)
            
    return ", ".join(reversed_list)

# --- POBIERANIE Z DIAGNOSTYKĄ ---
@st.cache_data(ttl=3600)
def get_elibri_xml(url, username, password):
    try:
        r = requests.get(url, auth=(username, password), timeout=15)
        if r.status_code == 200:
            return r.content
        elif r.status_code == 401:
            return "BŁĄD_AUTORYZACJI"
        elif r.status_code == 404:
            return "NIE_ZNALEZIONO"
        else:
            return f"BŁĄD_HTTP_{r.status_code}"
    except Exception as e:
        return f"BŁĄD_POŁĄCZENIA: {str(e)}"

# --- PARSER ONIX Z DYNAMICZNYM NAMESPACE ---
def parse_onix_data(xml_content):
    try:
        if not xml_content or isinstance(xml_content, str):
            return None
            
        root = ET.fromstring(xml_content)
        
        # Automatyczne wykrywanie Namespace z dokumentu
        ns_url = ""
        if '}' in root.tag:
            ns_url = root.tag.split('}')[0].strip('{')
        
        ns = {'onix': ns_url} if ns_url else {}

        # Szukanie produktu (obsługa braku namespace lub różnych wersji)
        product = root.find('.//onix:Product', ns) if ns else root.find('.//Product')
        
        if product is None:
            return {"BŁĄD_STRUKTURY": "XML nie zawiera sekcji Product (pusta odpowiedź)"}

        def get_text(path, parent=product):
            node = parent.find(path, ns)
            return node.text.strip() if node is not None and node.text else "Brak"

        # 1. ISBN
        isbn13 = "Brak"
        for ident in product.findall('.//onix:ProductIdentifier', ns):
            if get_text('onix:ProductIDType', ident) == "15":
                isbn13 = get_text('onix:IDValue', ident)

        # 2. Tytuł
        title = get_text('.//onix:TitleDetail[onix:TitleType="01"]//onix:TitleText')

        # 3. Autorzy
        authors = [c.find('onix:PersonName', ns).text for c in product.findall('.//onix:Contributor', ns) 
                   if c.find('onix:PersonName', ns) is not None]
        authors_str = ", ".join(authors) if authors else "Nieznany"

        # 4. Seria
        series_names = [s.find('.//onix:TitleText', ns).text for s in product.findall('.//onix:Collection', ns) 
                        if s.find('.//onix:TitleText', ns) is not None]
        series_str = ", ".join(series_names) if series_names else "Brak serii"

        # 5. Język
        lang_node = product.find('.//onix:Language[onix:LanguageRole="01"]/onix:LanguageCode', ns)
        lang_code = lang_node.text.strip() if lang_node is not None else "Brak"
        language = LANG_MAP.get(lang_code.lower(), lang_code)

        # 6. Data Premiery
        pub_date_raw = get_text('.//onix:PublishingDate[onix:PublishingDateRole="01"]/onix:Date')
        pub_date = f"{pub_date_raw[:4]}-{pub_date_raw[4:6]}-{pub_date_raw[6:]}" if len(pub_date_raw) == 8 else pub_date_raw

        # 7. Okładka i Opis
        cover_url = "Brak linku"
        for res in product.findall('.//onix:SupportingResource', ns):
            if get_text('onix:ResourceContentType', res) == "01":
                link_node = res.find('.//onix:ResourceLink', ns)
                if link_node is not None: cover_url = link_node.text.strip()

        desc = "Brak opisu"
        text_content = product.find('.//onix:TextContent[onix:TextType="03"]/onix:Text', ns)
        if text_content is not None:
            desc = re.sub('<[^<]+?>', '', text_content.text or "").strip()

        publisher = get_text('.//onix:Publisher/onix:PublisherName')
        pages = get_text('.//onix:Extent[onix:ExtentType="00"]/onix:ExtentValue')
        
        return {
            "Tytuł": title, "Autorzy": authors_str, "Język": language,
            "Seria": series_str, "Data premiery": pub_date, "Wydawca": publisher,
            "Liczba stron": pages, "ISBN-13": isbn13, "Opis": desc[:500] + "...",
            "Link do okładki": cover_url
        }
    except Exception as e:
        return {"BŁĄD_PARSERA": str(e)}

# --- UI ---
with st.sidebar:
    st.header("🔑 Autoryzacja eLibri")
    elibri_user = st.text_input("Username", value="empik")
    elibri_pass = st.text_input("Password", type="password", value="sjdhg235!S")

st.title("📖 Bibliotekarz Pro")
uploaded_file = st.file_uploader("Załaduj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę ISBN:", df_in.columns)
    
    if st.button("Rozpocznij proces"):
        final_data = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, row in df_in.iterrows():
            # Czyszczenie ISBN (usuwanie .0 i znaków niebędących cyframi)
            raw_isbn = str(row[target_col]).split('.')[0]
            isbn = re.sub(r'\D', '', raw_isbn).strip()
            
            status_text.text(f"Przetwarzanie: {isbn} ({i+1}/{len(df_in)})")
            
            xml_res = get_elibri_xml(f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn}", elibri_user, elibri_pass)
            
            error_msg = None
            if isinstance(xml_res, str) and "BŁĄD" in xml_res:
                error_msg = xml_res
            elif xml_res == "NIE_ZNALEZIONO":
                error_msg = "Brak ISBN w bazie"
            else:
                book_info = parse_onix_data(xml_res)
                if book_info and "BŁĄD_STRUKTURY" in book_info:
                    error_msg = "Błąd danych XML (pusty produkt)"
                elif book_info and "BŁĄD_PARSERA" in book_info:
                    error_msg = f"Błąd parsera: {book_info['BŁĄD_PARSERA']}"

            entry = {"Identyfikator": isbn}
            headers = ["Tytuł", "Autorzy", "Język", "Seria", "Data premiery", "Wydawca", "Liczba stron", "ISBN-13", "Opis", "Link do okładki"]
            
            if error_msg:
                for h in headers: entry[h] = error_msg
                entry["Autorzy (odwróceni)"] = error_msg
            else:
                for h in headers: entry[h] = book_info.get(h, "Brak")
                entry["Autorzy (odwróceni)"] = reverse_authors(entry["Autorzy"])
            
            final_data.append(entry)
            time.sleep(0.1) # Ochrona przed blokadą IP
            progress_bar.progress((i + 1) / len(df_in))

        res_df = pd.DataFrame(final_data)
        st.session_state.results_df = res_df
        status_text.success("Gotowe!")

if 'results_df' in st.session_state:
    st.dataframe(st.session_state.results_df)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    st.download_button("📥 Pobierz Rejestr", buf.getvalue(), "rejestr.xlsx")
