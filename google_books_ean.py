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
        r = requests.get(url, auth=(username, password), timeout=15)
        if r.status_code == 200:
            return r.content
        elif r.status_code == 401:
            return "BŁĄD_AUTH"
    except Exception:
        return None
    return None

# --- PARSER ONIX ---
def parse_onix_data(xml_content):
    try:
        root = ET.fromstring(xml_content)
        product = root.find('.//onix:Product', NS)
        if product is None: return None

        # Bardziej elastyczna funkcja wyciągania tekstu
        def find_text(tag_name, parent=product):
            node = parent.find(f'.//onix:{tag_name}', NS)
            return node.text.strip() if node is not None and node.text else "Brak"

        # 1. Tytuł i ISBN
        title = find_text('TitleText')
        isbn13 = "Brak"
        for ident in product.findall('.//onix:ProductIdentifier', NS):
            if find_text('ProductIDType', ident) == "15":
                isbn13 = find_text('IDValue', ident)

        # 2. Autorzy
        authors = [c.find('onix:PersonName', NS).text for c in product.findall('.//onix:Contributor', NS) 
                   if c.find('onix:PersonName', NS) is not None]
        authors_str = ", ".join(authors) if authors else "Nieznany"

        # 3. Seria
        coll = product.find('.//onix:Collection', NS)
        series_str = coll.find('.//onix:TitleText', NS).text if coll is not None and coll.find('.//onix:TitleText', NS) is not None else "Brak serii"

        # 4. Opis wydania (EditionStatement)
        ed_stat = find_text('EditionStatement')
        ed_num = find_text('EditionNumber')
        
        if ed_stat != "Brak":
            edition_display = "Pierwsze" if ed_stat == "1" else ed_stat
        elif ed_num != "Brak":
            edition_display = "Pierwsze" if ed_num == "1" else f"Wydanie {ed_num}"
        else:
            edition_display = "Brak informacji"

        # 5. Język
        lang_node = product.find('.//onix:LanguageCode', NS)
        language = lang_node.text if lang_node is not None else "pol"

        # 6. Data Premiery
        pub_date_raw = find_text('Date')
        if pub_date_raw == "Brak":
            pub_date_raw = find_text('PublishingDate')
        
        if len(pub_date_raw) == 8 and pub_date_raw.isdigit():
            pub_date = f"{pub_date_raw[:4]}-{pub_date_raw[4:6]}-{pub_date_raw[6:]}"
        else:
            pub_date = pub_date_raw

        # 7. Okładka
        cover_url = "Brak linku"
        for res in product.findall('.//onix:SupportingResource', NS):
            if find_text('ResourceContentType', res) == "01":
                link = res.find('.//onix:ResourceLink', NS)
                if link is not None: cover_url = link.text.strip()

        # 8. Techniczne
        publisher = find_text('PublisherName')
        pages = find_text('ExtentValue')

        return {
            "Tytuł": title, "Autorzy": authors_str, "Język": language, "Seria": series_str,
            "Opis wydania": edition_display, "Data premiery": pub_date, "Wydawca": publisher,
            "Liczba stron": pages, "ISBN-13": isbn13, "Link do okładki": cover_url
        }
    except Exception as e:
        st.warning(f"Błąd parsowania jednego z produktów: {e}")
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
    
    if st.button("Rozpocznij pobieranie"):
        final_data = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        headers = ["Tytuł", "Autorzy", "Język", "Seria", "Opis wydania", "Data premiery", "Wydawca", "Liczba stron", "ISBN-13", "Link do okładki"]
        
        for i, row in df_in.iterrows():
            # CZYSZCZENIE ISBN - usuwa wszystko poza cyframi
            isbn_raw = str(row[target_col]).split('.')[0].strip()
            isbn = "".join(filter(str.isdigit, isbn_raw))
            
            status_text.text(f"Przetwarzanie: {isbn} ({i+1}/{len(df_in)})")
            
            xml_res = get_elibri_xml(f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn}", elibri_user, elibri_pass)
            
            if xml_res == "BŁĄD_AUTH":
                st.error("Błąd autoryzacji!")
                st.stop()
            
            book_info = parse_onix_data(xml_res) if xml_res else None
            
            entry = {"ISBN wejściowy": isbn}
            for h in headers:
                entry[h] = book_info.get(h, "Nie znaleziono") if book_info else "Nie znaleziono w eLibri"
            
            entry["Autorzy (odwróceni)"] = reverse_authors(entry.get("Autorzy", ""))
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))

        res_df = pd.DataFrame(final_data)
        
        # Przesunięcie kolumny autorów
        if "Autorzy" in res_df.columns:
            cols = list(res_df.columns)
            idx = cols.index("Autorzy")
            cols.insert(idx + 1, cols.pop(cols.index("Autorzy (odwróceni)")))
            res_df = res_df[cols]

        st.session_state.results_df = res_df
        st.success("Gotowe!")

if 'results_df' in st.session_state:
    st.dataframe(st.session_state.results_df)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    st.download_button("📥 Pobierz Rejestr", buf.getvalue(), "rejestr.xlsx")
