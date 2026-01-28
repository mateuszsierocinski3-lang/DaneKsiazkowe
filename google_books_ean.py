import streamlit as st
import pandas as pd
import requests
import re
import io
import xml.etree.ElementTree as ET

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz - Debug", page_icon="📖", layout="wide")

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

def get_elibri_xml(url, username, password):
    try:
        r = requests.get(url, auth=(username, password), timeout=10)
        return r.status_code, r.content
    except Exception as e:
        return "Error", str(e)

def parse_onix_data(xml_content):
    try:
        root = ET.fromstring(xml_content)
        ns_url = root.tag.split('}')[0].strip('{') if '}' in root.tag else ""
        ns = {'onix': ns_url} if ns_url else {}

        product = root.find('.//onix:Product', ns)
        if product is None:
            return "BRAK_PRODUKTU"

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

        # 4. Pozostałe pola
        publisher = get_text('.//onix:Publisher/onix:PublisherName')
        pages = get_text('.//onix:Extent[onix:ExtentType="00"]/onix:ExtentValue')
        
        return {
            "Tytuł": title,
            "Autorzy": authors_str,
            "Wydawca": publisher,
            "Liczba stron": pages,
            "ISBN-13": isbn13,
            "Status": "OK"
        }
    except Exception as e:
        return f"BŁĄD_PARSERA: {str(e)}"

# --- UI ---
st.title("📖 Bibliotekarz - Tryb Diagnostyczny")

with st.sidebar:
    st.header("🔑 Autoryzacja")
    elibri_user = st.text_input("User", value="empik")
    elibri_pass = st.text_input("Pass", type="password", value="sjdhg235!S")

# --- SEKCJA DIAGNOSTYCZNA (Pojedynczy ISBN) ---
st.subheader("🔍 Testuj jeden ISBN")
test_isbn = st.text_input("Wpisz ISBN do sprawdzenia:", "9788384258644")
if st.button("Sprawdź co widzi API"):
    clean_isbn = re.sub(r'[^0-9]', '', test_isbn)
    url = f"https://www.elibri.com.pl/distributors/empik/by_isbn/{clean_isbn}"
    code, content = get_elibri_xml(url, elibri_user, elibri_pass)
    
    st.write(f"Kod odpowiedzi HTTP: **{code}**")
    if code == 200:
        st.info("Otrzymano dane. Poniżej surowy kod XML:")
        st.code(content.decode('utf-8'), language='xml')
        parsed = parse_onix_data(content)
        st.write("Wynik parsera:", parsed)
    else:
        st.error(f"Błąd połączenia. Treść: {content}")

st.divider()

# --- PRZETWARZANIE PLIKU ---
st.subheader("📊 Przetwarzaj plik Excel")
uploaded_file = st.file_uploader("Załaduj plik", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Kolumna z ISBN:", df_in.columns)
    
    if st.button("Uruchom masowe pobieranie"):
        final_data = []
        progress = st.progress(0)
        
        for i, row in df_in.iterrows():
            isbn_raw = str(row[target_col]).split('.')[0].strip()
            isbn = re.sub(r'[^0-9]', '', isbn_raw)
            url = f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn}"
            
            code, content = get_elibri_xml(url, elibri_user, elibri_pass)
            
            if code == 200:
                book_info = parse_onix_data(content)
                if isinstance(book_info, dict):
                    entry = book_info
                else:
                    entry = {"Tytuł": book_info, "Status": "Błąd danych"}
            else:
                entry = {"Tytuł": f"Błąd HTTP {code}", "Status": "Błąd połączenia"}
            
            entry["Identyfikator"] = isbn
            final_data.append(entry)
            progress.progress((i + 1) / len(df_in))

        res_df = pd.DataFrame(final_data)
        st.session_state.results_df = res_df
        st.dataframe(res_df)

if 'results_df' in st.session_state:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    st.download_button("📥 Pobierz Rejestr", buf.getvalue(), "rejestr.xlsx")
