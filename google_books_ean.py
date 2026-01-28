import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import xml.etree.ElementTree as ET

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz", page_icon="📖", layout="wide")

# --- MAPOWANIE JĘZYKÓW ---
LANG_MAP = {
    'pol': 'polski', 'eng': 'angielski', 'ger': 'niemiecki',
    'fre': 'francuski', 'rus': 'rosyjski', 'ita': 'włoski', 'spa': 'hiszpański'
}

# --- FUNKCJA ODWRACANIA AUTORÓW ---
def reverse_authors(authors_str):
    if not authors_str or authors_str in ["Nieznany", "Brak", "Błąd danych"]:
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

# --- CACHE ---
@st.cache_data(ttl=3600)
def get_elibri_xml(url, username, password):
    try:
        r = requests.get(url, auth=(username, password), timeout=10)
        if r.status_code == 200:
            return r.content
        elif r.status_code == 401:
            return "BŁĄD_AUTH"
        elif r.status_code == 404:
            return "BRAK_ISBN"
    except Exception:
        return None
    return None

# --- PARSER ONIX (Z AUTOMATYCZNYM NAMESPACE) ---
def parse_onix_data(xml_content):
    try:
        root = ET.fromstring(xml_content)
        
        # Automatyczne wykrywanie namespace z dokumentu
        ns_url = ""
        if '}' in root.tag:
            ns_url = root.tag.split('}')[0].strip('{')
        
        ns = {'onix': ns_url} if ns_url else {}

        product = root.find('.//onix:Product', ns)
        if product is None: return None

        def get_text(path, parent=product):
            node = parent.find(path, ns)
            return node.text.strip() if node is not None and node.text else "Brak"

        # 1. Identyfikatory
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
        lang_code = get_text('.//onix:Language[onix:LanguageRole="01"]/onix:LanguageCode')
        language = LANG_MAP.get(lang_code.lower(), lang_code) if lang_code != "Brak" else "Brak informacji"

        # 6. Opis wydania
        desc_detail = product.find('.//onix:DescriptiveDetail', ns)
        edition_display = "Brak informacji"
        if desc_detail is not None:
            ed_stat = get_text('onix:EditionStatement', desc_detail)
            if ed_stat != "Brak":
                edition_display = "Pierwsze" if ed_stat == "1" else ed_stat
            else:
                ed_num = get_text('onix:EditionNumber', desc_detail)
                if ed_num == "1": edition_display = "Pierwsze"
                elif ed_num != "Brak": edition_display = f"Wydanie {ed_num}"

        # 7. Data Premiery
        pub_date_raw = get_text('.//onix:PublishingDate[onix:PublishingDateRole="01"]/onix:Date')
        if pub_date_raw != "Brak" and len(pub_date_raw) == 8:
            pub_date = f"{pub_date_raw[:4]}-{pub_date_raw[4:6]}-{pub_date_raw[6:]}"
        else:
            pub_date = pub_date_raw

        # 8. Okładka
        cover_url = "Brak linku"
        for res in product.findall('.//onix:SupportingResource', ns):
            if get_text('onix:ResourceContentType', res) == "01":
                link_node = res.find('.//onix:ResourceLink', ns)
                if link_node is not None: cover_url = link_node.text.strip()

        # 9. Pozostałe
        description = "Brak opisu"
        text_content = product.find('.//onix:TextContent[onix:TextType="03"]/onix:Text', ns)
        if text_content is not None:
            raw_html = text_content.text or ""
            description = re.sub('<[^<]+?>', '', raw_html).strip()

        publisher = get_text('.//onix:Publisher/onix:PublisherName')
        pages = get_text('.//onix:Extent[onix:ExtentType="00"]/onix:ExtentValue')
        
        return {
            "Tytuł": title,
            "Autorzy": authors_str,
            "Język": language,
            "Seria": series_str,
            "Opis wydania": edition_display,
            "Data premiery": pub_date,
            "Wydawca": publisher,
            "Liczba stron": pages,
            "ISBN-13": isbn13,
            "Opis": description[:500] + "..." if len(description) > 500 else description,
            "Link do okładki": cover_url
        }
    except Exception:
        return None

# --- UI ---
with st.sidebar:
    st.header("🔑 Autoryzacja eLibri")
    elibri_user = st.text_input("Username (API)", value="empik")
    elibri_pass = st.text_input("Password (API)", type="password", value="sjdhg235!S")

st.title("📖 Bibliotekarz")

uploaded_file = st.file_uploader("Załaduj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę ISBN:", df_in.columns)
    
    if st.button("Rozpocznij proces"):
        final_data = []
        progress_bar = st.progress(0)
        
        headers = ["Tytuł", "Autorzy", "Język", "Seria", "Opis wydania", "Data premiery", "Wydawca", "Liczba stron", "ISBN-13", "Opis", "Link do okładki"]
        
        for i, row in df_in.iterrows():
            # Oczyszczanie ISBN ze zbędnych znaków
            isbn_raw = str(row[target_col]).split('.')[0].strip()
            isbn = re.sub(r'[^0-9]', '', isbn_raw)
            
            xml_res = get_elibri_xml(f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn}", elibri_user, elibri_pass)
            
            if xml_res == "BŁĄD_AUTH":
                status = "Błąd autoryzacji"
                book_info = None
            elif xml_res == "BRAK_ISBN":
                status = "Nie znaleziono ISBN"
                book_info = None
            elif xml_res is None:
                status = "Błąd połączenia"
                book_info = None
            else:
                book_info = parse_onix_data(xml_res)
                status = "Błąd danych" if not book_info else "OK"
            
            entry = {"Identyfikator": isbn}
            for h in headers:
                if book_info:
                    entry[h] = book_info.get(h, "Brak")
                else:
                    entry[h] = status
            
            entry["Autorzy (odwróceni)"] = reverse_authors(entry["Autorzy"])
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))

        res_df = pd.DataFrame(final_data)
        
        cols = list(res_df.columns)
        if "Autorzy" in cols and "Autorzy (odwróceni)" in cols:
            idx = cols.index("Autorzy")
            cols.insert(idx + 1, cols.pop(cols.index("Autorzy (odwróceni)")))
            res_df = res_df[cols]

        st.session_state.results_df = res_df
        st.success("Proces zakończony!")

if 'results_df' in st.session_state and st.session_state.results_df is not None:
    st.dataframe(st.session_state.results_df)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    st.download_button("📥 Pobierz Rejestr", buf.getvalue(), "rejestr_bibliotekarz.xlsx")
