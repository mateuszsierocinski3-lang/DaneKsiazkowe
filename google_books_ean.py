import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import xml.etree.ElementTree as ET

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz", page_icon="📖", layout="wide")

# Funkcja pomocnicza do bezpiecznego pobierania tekstu z zagnieżdżonych struktur
def find_text(parent, path, ns=None):
    node = parent.find(path, ns)
    return node.text.strip() if node is not None and node.text else None

# --- PARSER ONIX ---
def parse_onix_data(xml_content):
    try:
        # eLibri czasem zwraca XML z zadeklarowanym namespace, a czasem bez.
        # Obsłużymy oba przypadki usuwając namespace dla ułatwienia parsowania.
        xml_content_str = xml_content.decode('utf-8') if isinstance(xml_content, bytes) else xml_content
        # Usuwamy deklaracje xmlns, aby xpath był prostszy
        xml_content_str = re.sub(r'\sxmlns="[^"]+"', '', xml_content_str, count=1)
        root = ET.fromstring(xml_content_str)
        
        # Szukamy produktu (może być rootem lub wewnątrz paczki ONIXMessage)
        product = root if root.tag == 'Product' else root.find('.//Product')
        if product is None: return None

        # 1. Identyfikatory (ISBN-13)
        isbn13 = "Nie znaleziono"
        for ident in product.findall('.//ProductIdentifier'):
            if find_text(ident, 'ProductIDType') == "15":
                isbn13 = find_text(ident, 'IDValue')

        # 2. Tytuł (zgodnie z Twoim XML: TitleDetail -> TitleElement -> TitleText)
        title = "Brak tytułu"
        title_detail = product.find('.//TitleDetail[TitleType="01"]')
        if title_detail is not None:
            title = find_text(title_detail, './/TitleText')

        # 3. Autorzy
        authors = []
        for contrib in product.findall('.//Contributor'):
            name = find_text(contrib, 'PersonName')
            if name: authors.append(name)
        authors_str = ", ".join(authors) if authors else "Nieznany"

        # 4. Seria Wydawnicza
        series = []
        for coll in product.findall('.//Collection'):
            s_name = find_text(coll, './/TitleText')
            if s_name: series.append(s_name)
        series_str = ", ".join(series) if series else "Brak serii"

        # 5. Opis wydania i Liczba stron
        desc_detail = product.find('DescriptiveDetail')
        edition = "Brak"
        pages = "Brak"
        if desc_detail is not None:
            edition = find_text(desc_detail, 'EditionStatement') or "1"
            if edition == "1": edition = "Pierwsze"
            
            pages = find_text(desc_detail, './/Extent[ExtentType="00"]/ExtentValue')

        # 6. Opis (CollateralDetail -> TextContent -> Text)
        description = "Brak opisu"
        text_node = product.find('.//TextContent[TextType="03"]/Text')
        if text_node is not None:
            # Pobieramy tekst (w tym CDATA)
            raw_text = text_node.text or ""
            description = re.sub('<[^<]+?>', '', raw_text).strip()

        # 7. Okładka (ResourceLink)
        cover_url = "Brak okładki"
        res_link = product.find('.//SupportingResource[ResourceContentType="01"]//ResourceLink')
        if res_link is not None:
            cover_url = res_link.text

        # 8. Wydawca i Cena
        pub_name = find_text(product, './/Publisher/PublisherName') or "Brak"
        imprint = find_text(product, './/Imprint/ImprintName') or "Brak"
        
        price_node = product.find('.//Price[PriceType="02"]')
        price_str = "Brak"
        if price_node is not None:
            amt = find_text(price_node, 'PriceAmount')
            cur = find_text(price_node, 'CurrencyCode')
            price_str = f"{amt} {cur}"

        return {
            "Tytuł": title,
            "Autorzy": authors_str,
            "Seria": series_str,
            "Opis wydania": edition,
            "Wydawca": pub_name,
            "Imprint": imprint,
            "Liczba stron": pages,
            "ISBN-13": isbn13,
            "Cena": price_str,
            "Opis": (description[:500] + "...") if len(description) > 500 else description,
            "Link do okładki": cover_url
        }
    except Exception as e:
        st.error(f"Błąd parsowania: {e}")
        return None

# --- UI (Pozostała część bez zmian, poza drobną korektą w pętli) ---
with st.sidebar:
    st.header("🔑 Autoryzacja eLibri")
    elibri_user = st.text_input("Username (API)", value="empik")
    elibri_pass = st.text_input("Password (API)", type="password", value="sjdhg235!S")

st.title("📖 Bibliotekarz v2 (ONIX Parser)")

uploaded_file = st.file_uploader("Załaduj plik Excel z ISBNami", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę zawierającą ISBN:", df_in.columns)
    
    if st.button("Rozpocznij pobieranie danych"):
        final_data = []
        progress_bar = st.progress(0)
        
        # Cache dla API (funkcja z oryginalnego skryptu st.cache_data)
        @st.cache_data(ttl=3600)
        def fetch_xml(isbn, user, pwd):
            url = f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn}"
            try:
                r = requests.get(url, auth=(user, pwd), timeout=10)
                return r.content if r.status_code == 200 else None
            except: return None

        for i, row in df_in.iterrows():
            isbn = str(row[target_col]).replace('.0', '').strip()
            xml_content = fetch_xml(isbn, elibri_user, elibri_pass)
            
            book_info = parse_onix_data(xml_content) if xml_content else None
            
            entry = {"ISBN wejściowy": isbn}
            headers = ["Tytuł", "Autorzy", "Seria", "Opis wydania", "Wydawca", "Imprint", "Liczba stron", "ISBN-13", "Cena", "Opis", "Link do okładki"]
            
            if book_info:
                for h in headers:
                    entry[h] = book_info.get(h, "Brak danych")
            else:
                for h in headers:
                    entry[h] = "Nie znaleziono w eLibri"
            
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            time.sleep(0.1)

        st.session_state.results_df = pd.DataFrame(final_data)
        st.success("Zakończono pobieranie!")

if 'results_df' in st.session_state:
    st.dataframe(st.session_state.results_df)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    st.download_button("📥 Pobierz Rejestr (XLSX)", buf.getvalue(), "rejestr_elibri.xlsx")
