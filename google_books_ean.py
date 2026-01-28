import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random
import xml.etree.ElementTree as ET

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz eLibri ONIX", page_icon="📖", layout="wide")

# --- NAMESPACE ONIX ---
# eLibri używa standardu ONIX 3.0/3.1
NS = {'onix': 'http://ns.editeur.org/onix/3.1/reference'}

# --- CACHE ---
@st.cache_data(ttl=3600)
def get_elibri_xml(url, username, password):
    try:
        r = requests.get(url, auth=(username, password), timeout=10)
        if r.status_code == 200:
            return r.content  # Zwracamy surowe dane binarne (XML)
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

        # Funkcja pomocnicza do szukania tekstu w tagach
        def get_text(path, parent=product):
            node = parent.find(path, NS)
            return node.text.strip() if node is not None and node.text else "Brak"

        # 1. Identyfikatory (ISBN-13 / EAN)
        isbn13 = "Brak"
        for ident in product.findall('.//onix:ProductIdentifier', NS):
            id_type = get_text('onix:ProductIDType', ident)
            if id_type == "15": # ISBN-13 / EAN
                isbn13 = get_text('onix:IDValue', ident)

        # 2. Tytuł
        title = get_text('.//onix:TitleDetail[onix:TitleType="01"]//onix:TitleText')

        # 3. Autor
        authors = []
        for contrib in product.findall('.//onix:Contributor', NS):
            name = get_text('onix:PersonName', contrib)
            if name != "Brak": authors.append(name)
        authors_str = ", ".join(authors) if authors else "Nieznany"

        # 4. Opis (CDATA z sekcji TextContent)
        description = "Brak opisu"
        text_content = product.find('.//onix:TextContent[onix:TextType="03"]/onix:Text', NS)
        if text_content is not None:
            # Usuwamy tagi HTML z opisu dla czystości Excela
            raw_html = text_content.text or ""
            description = re.sub('<[^<]+?>', '', raw_html).strip()

        # 5. Okładka (Link)
        cover_url = "Brak okładki"
        for res in product.findall('.//onix:SupportingResource', NS):
            if get_text('onix:ResourceContentType', res) == "01": # Front cover
                link = res.find('.//onix:ResourceLink', NS)
                if link is not None: cover_url = link.text

        # 6. Wydawca i Imprint
        publisher = get_text('.//onix:Publisher/onix:PublisherName')
        imprint = get_text('.//onix:Imprint/onix:ImprintName')

        # 7. Cena i strony
        pages = get_text('.//onix:Extent[onix:ExtentType="00"]/onix:ExtentValue')
        price = get_text('.//onix:Price[onix:PriceType="02"]/onix:PriceAmount')
        currency = get_text('.//onix:Price[onix:PriceType="02"]/onix:CurrencyCode')

        return {
            "Tytuł": title,
            "Autorzy": authors_str,
            "Wydawca": publisher,
            "Imprint": imprint,
            "Liczba stron": pages,
            "ISBN-13": isbn13,
            "Cena": f"{price} {currency}" if price != "Brak" else "Brak",
            "Opis": description[:500] + "..." if len(description) > 500 else description,
            "Link do okładki": cover_url
        }
    except Exception as e:
        print(f"Błąd parsowania: {e}")
        return None

# --- UI (SIDEBAR & STYLE) ---
with st.sidebar:
    st.header("🔑 Autoryzacja eLibri")
    elibri_user = st.text_input("Username (API)", value="empik")
    elibri_pass = st.text_input("Password (API)", type="password", value="sjdhg235!S")

st.title("📖 Bibliotekarz eLibri (ONIX Parser)")

uploaded_file = st.file_uploader("Załaduj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę ISBN:", df_in.columns)
    
    if st.button("Rozpocznij pobieranie danych ONIX"):
        if not elibri_user or not elibri_pass:
            st.error("Podaj dane logowania!")
        else:
            final_data = []
            progress_bar = st.progress(0)
            
            for i, row in df_in.iterrows():
                isbn = str(row[target_col]).split('.')[0] # usuwanie .0 z Excela
                xml_res = get_elibri_xml(f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn}", elibri_user, elibri_pass)
                
                if xml_res == "BŁĄD_AUTH":
                    st.error("Błędne dane logowania!")
                    st.stop()
                
                book_info = parse_onix_data(xml_res) if xml_res else None
                
                entry = {"Identyfikator": isbn}
                headers = ["Tytuł", "Autorzy", "Wydawca", "Imprint", "Liczba stron", "ISBN-13", "Cena", "Opis", "Link do okładki"]
                
                for h in headers:
                    entry[h] = book_info.get(h, "Nie znaleziono") if book_info else "Błąd danych"
                
                final_data.append(entry)
                progress_bar.progress((i + 1) / len(df_in))
                time.sleep(0.1)

            st.session_state.results_df = pd.DataFrame(final_data)
            st.success("Skatalogowano!")

if 'results_df' in st.session_state and st.session_state.results_df is not None:
    st.dataframe(st.session_state.results_df)
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    st.download_button("📥 Pobierz Rejestr", buf.getvalue(), "rejestr_elibri.xlsx")
