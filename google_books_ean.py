import streamlit as st
import pandas as pd
import requests
import re
import io
import xml.etree.ElementTree as ET

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz PRO", page_icon="📖", layout="wide")

# --- MAPOWANIE JĘZYKÓW ---
LANG_MAP = {
    'pol': 'polski', 'eng': 'angielski', 'ger': 'niemiecki',
    'fre': 'francuski', 'rus': 'rosyjski', 'ita': 'włoski', 'spa': 'hiszpański'
}

def reverse_authors(authors_str):
    if not authors_str or authors_str in ["Nieznany", "Brak", "Błąd danych"]:
        return authors_str
    individual_authors = [a.strip() for a in authors_str.split(',')]
    reversed_list = []
    for author in individual_authors:
        parts = author.split()
        if len(parts) >= 2:
            reversed_list.append(f"{parts[-1]} {' '.join(parts[:-1])}")
        else:
            reversed_list.append(author)
    return ", ".join(reversed_list)

def clean_isbn_logic(raw_val):
    """Czyści ISBN z formatowania Excelowego (kropki, E+12, spacje)."""
    val = str(raw_val).strip()
    if '.' in val:
        val = val.split('.')[0]
    val = re.sub(r'[^0-9]', '', val)
    return val

def get_elibri_xml(url, username, password):
    try:
        r = requests.get(url, auth=(username, password), timeout=15)
        if r.status_code == 200:
            return r.content
        elif r.status_code == 401:
            return "BŁĄD_AUTH"
        elif r.status_code == 404:
            return "BRAK_ISBN"
        return f"BŁĄD_HTTP_{r.status_code}"
    except Exception:
        return None

def parse_onix_data(xml_content):
    try:
        # Usuwanie namespace dla maksymalnej kompatybilności
        xml_string = xml_content.decode('utf-8')
        xml_string = re.sub(r'\sxmlns="[^"]+"', '', xml_string)
        xml_string = re.sub(r'\sxmlns:onix="[^"]+"', '', xml_string)
        xml_string = xml_string.replace('onix:', '')
        
        root = ET.fromstring(xml_string.encode('utf-8'))
        product = root.find('.//Product')
        if product is None: return None

        def get_text(path, parent=product):
            node = parent.find(path)
            return node.text.strip() if node is not None and node.text else "Brak"

        # Tytuł
        title = get_text('.//TitleDetail[TitleType="01"]//TitleText')

        # Autorzy
        authors = [c.find('PersonName').text for c in product.findall('.//Contributor') 
                   if c.find('PersonName') is not None]
        authors_str = ", ".join(authors) if authors else "Nieznany"

        # Seria
        series = [s.find('.//TitleText').text for s in product.findall('.//Collection') 
                  if s.find('.//TitleText') is not None]
        series_str = ", ".join(series) if series else "Brak serii"

        # Wydawca i Strony
        publisher = get_text('.//Publisher/PublisherName')
        pages = get_text('.//Extent[ExtentType="00"]/ExtentValue')
        
        # ISBN-13 z XML
        isbn13 = "Brak"
        for ident in product.findall('.//ProductIdentifier'):
            if get_text('ProductIDType', ident) == "15":
                isbn13 = get_text('IDValue', ident)

        return {
            "Tytuł": title,
            "Autorzy": authors_str,
            "Seria": series_str,
            "Wydawca": publisher,
            "Liczba stron": pages,
            "ISBN-13": isbn13
        }
    except Exception:
        return None

# --- UI ---
st.title("📖 Bibliotekarz PRO")

with st.sidebar:
    st.header("🔑 Autoryzacja")
    elibri_user = st.text_input("User", value="empik")
    elibri_pass = st.text_input("Pass", type="password", value="sjdhg235!S")

uploaded_file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę z ISBN:", df_in.columns)
    
    if st.button("Pobierz dane"):
        final_results = []
        progress = st.progress(0)
        
        for i, row in df_in.iterrows():
            clean_isbn = clean_isbn_logic(row[target_col])
            
            if not clean_isbn or len(clean_isbn) < 10:
                result = {"Identyfikator": clean_isbn, "Tytuł": "Błędny format ISBN w Excelu"}
            else:
                url = f"https://www.elibri.com.pl/distributors/empik/by_isbn/{clean_isbn}"
                xml_raw = get_elibri_xml(url, elibri_user, elibri_pass)
                
                if isinstance(xml_raw, bytes):
                    data = parse_onix_data(xml_raw)
                    if data:
                        result = data
                        result["Status"] = "OK"
                    else:
                        result = {"Tytuł": "Brak danych w XML (pusty produkt)", "Status": "Błąd"}
                else:
                    status_msg = str(xml_raw) if xml_raw else "Błąd połączenia"
                    result = {"Tytuł": status_msg, "Status": "Błąd"}
            
            result["Identyfikator"] = clean_isbn
            if "Autorzy" in result:
                result["Autorzy (odwróceni)"] = reverse_authors(result["Autorzy"])
            
            final_results.append(result)
            progress.progress((i + 1) / len(df_in))

        res_df = pd.DataFrame(final_results)
        
        # Porządkowanie kolumn
        cols = ["Identyfikator", "Tytuł", "Autorzy", "Autorzy (odwróceni)", "Wydawca", "Seria", "Liczba stron", "ISBN-13", "Status"]
        res_df = res_df.reindex(columns=cols)
        
        st.session_state.results_df = res_df
        st.success("Gotowe!")

if 'results_df' in st.session_state:
    st.dataframe(st.session_state.results_df)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    st.download_button("📥 Pobierz gotowy Excel", buf.getvalue(), "wynik_bibliotekarz.xlsx")
