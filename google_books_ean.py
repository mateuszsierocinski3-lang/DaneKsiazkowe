import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import xml.etree.ElementTree as ET

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz", page_icon="📖", layout="wide")

# --- NAMESPACE ONIX ---
NS = {'onix': 'http://ns.editeur.org/onix/3.1/reference'}

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

# --- POBIERANIE XML Z DIAGNOSTYKĄ ---
@st.cache_data(ttl=3600)
def get_elibri_xml(url, username, password):
    try:
        r = requests.get(url, auth=(username, password), timeout=15)
        if r.status_code == 200:
            return {"status": "OK", "content": r.content}
        elif r.status_code == 401:
            return {"status": "BŁĄD_AUTORYZACJI (401)", "content": None}
        elif r.status_code == 403:
            return {"status": "DOSTĘP_ZABLOKOWANY (403)", "content": None}
        else:
            return {"status": f"BŁĄD_HTTP_{r.status_code}", "content": None}
    except Exception as e:
        return {"status": f"BŁĄD_POŁĄCZENIA: {str(e)}", "content": None}

# --- PARSER ONIX (Pancerny) ---
def parse_onix_data(xml_content):
    try:
        root = ET.fromstring(xml_content)
        product = root.find('.//onix:Product', NS)
        if product is None: return None

        def get_val(tag_name, parent=product):
            node = parent.find(f'.//onix:{tag_name}', NS)
            return node.text.strip() if node is not None and node.text else "Brak"

        # 1. Tytuł i ISBN
        title = get_val('TitleText')
        isbn13 = "Brak"
        for ident in product.findall('.//onix:ProductIdentifier', NS):
            if get_val('ProductIDType', ident) == "15":
                isbn13 = get_val('IDValue', ident)

        # 2. Autorzy
        authors = [c.find('onix:PersonName', NS).text for c in product.findall('.//onix:Contributor', NS) 
                   if c.find('onix:PersonName', NS) is not None]
        authors_str = ", ".join(authors) if authors else "Nieznany"

        # 3. Język
        lang_node = product.find('.//onix:LanguageCode', NS)
        lang_code = lang_node.text.lower() if lang_node is not None else "pol"
        language = LANG_MAP.get(lang_code, lang_code)

        # 4. Seria
        coll = product.find('.//onix:Collection', NS)
        series_str = coll.find('.//onix:TitleText', NS).text if coll is not None and coll.find('.//onix:TitleText', NS) is not None else "Brak serii"

        # 5. Opis wydania (EditionStatement)
        ed_stat = get_val('EditionStatement')
        ed_num = get_val('EditionNumber')
        if ed_stat != "Brak":
            edition_final = "Pierwsze" if ed_stat == "1" else ed_stat
        elif ed_num != "Brak":
            edition_final = "Pierwsze" if ed_num == "1" else f"Wydanie {ed_num}"
        else:
            edition_final = "Brak informacji"

        # 6. Data Premiery
        pub_date_raw = get_val('Date')
        if pub_date_raw == "Brak": pub_date_raw = get_val('PublishingDate')
        pub_date = f"{pub_date_raw[:4]}-{pub_date_raw[4:6]}-{pub_date_raw[6:]}" if len(pub_date_raw) == 8 else pub_date_raw

        # 7. Okładka i Opis
        cover_url = "Brak linku"
        for res in product.findall('.//onix:SupportingResource', NS):
            if get_val('ResourceContentType', res) == "01":
                link = res.find('.//onix:ResourceLink', NS)
                if link is not None: cover_url = link.text.strip()

        publisher = get_val('PublisherName')
        pages = get_val('ExtentValue')
        
        return {
            "Tytuł": title, "Autorzy": authors_str, "Język": language, "Seria": series_str,
            "Opis wydania": edition_final, "Data premiery": pub_date, "Wydawca": publisher,
            "Liczba stron": pages, "ISBN-13": isbn13, "Link do okładki": cover_url
        }
    except:
        return None

# --- UI ---
st.title("📖 Bibliotekarz")

with st.sidebar:
    st.header("🔑 Autoryzacja")
    elibri_user = st.text_input("User", value="empik")
    elibri_pass = st.text_input("Pass", type="password", value="sjdhg235!S")

uploaded_file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Kolumna ISBN:", df_in.columns)
    
    if st.button("Pobierz dane"):
        final_data = []
        progress = st.progress(0)
        status_msg = st.empty()
        
        headers = ["Tytuł", "Autorzy", "Język", "Seria", "Opis wydania", "Data premiery", "Wydawca", "Liczba stron", "ISBN-13", "Link do okładki"]
        
        for i, row in df_in.iterrows():
            # Czyszczenie ISBN (same cyfry)
            isbn_raw = str(row[target_col]).split('.')[0].strip()
            isbn = "".join(filter(str.isdigit, isbn_raw))
            
            res = get_elibri_xml(f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn}", elibri_user, elibri_pass)
            
            if res["status"] != "OK":
                status_msg.error(f"Problemy z połączeniem: {res['status']}")
            
            info = parse_onix_data(res["content"]) if res["content"] else None
            
            entry = {"ISBN wejściowy": isbn}
            for h in headers:
                if info:
                    entry[h] = info.get(h, "Brak danych")
                else:
                    entry[h] = f"Błąd: {res['status']}"
            
            entry["Autorzy (odwróceni)"] = reverse_authors(entry.get("Autorzy", ""))
            final_data.append(entry)
            progress.progress((i + 1) / len(df_in))

        res_df = pd.DataFrame(final_data)
        
        # Przesunięcie kolumny 'Autorzy (odwróceni)' obok 'Autorzy'
        if "Autorzy" in res_df.columns:
            cols = list(res_df.columns)
            idx = cols.index("Autorzy")
            cols.insert(idx + 1, cols.pop(cols.index("Autorzy (odwróceni)")))
            res_df = res_df[cols]
            
        st.session_state.results_df = res_df
        st.dataframe(res_df)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            res_df.to_excel(writer, index=False)
        st.download_button("📥 Pobierz wynikowy Excel", buf.getvalue(), "rejestr_bibliotekarz.xlsx")
