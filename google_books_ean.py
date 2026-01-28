import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import xml.etree.ElementTree as ET

# --- KONFIGURACJA STRONY ---
# Zmieniono nazwę na "Bibliotekarz"
st.set_page_config(page_title="Bibliotekarz", page_icon="📖", layout="wide")

# --- NAMESPACE ONIX ---
NS = {'onix': 'http://ns.editeur.org/onix/3.1/reference'}

# --- CACHE ---
@st.cache_data(ttl=3600)
def get_elibri_xml(url, username, password):
    try:
        r = requests.get(url, auth=(username, password), timeout=10)
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

        def get_text(path, parent=product):
            node = parent.find(path, NS)
            return node.text.strip() if node is not None and node.text else "Brak"

        # 1. Identyfikatory
        isbn13 = "Brak"
        for ident in product.findall('.//onix:ProductIdentifier', NS):
            id_type = get_text('onix:ProductIDType', ident)
            if id_type == "15":
                isbn13 = get_text('onix:IDValue', ident)

        # 2. Tytuł
        title = get_text('.//onix:TitleDetail[onix:TitleType="01"]//onix:TitleText')

        # 3. Autorzy
        authors = []
        for contrib in product.findall('.//onix:Contributor', NS):
            name = get_text('onix:PersonName', contrib)
            if name != "Brak": authors.append(name)
        authors_str = ", ".join(authors) if authors else "Nieznany"

        # 4. NOWE: Seria Wydawnicza
        series_names = []
        for series in product.findall('.//onix:Collection', NS):
            # Szukamy tytułu kolekcji/serii
            s_title = series.find('.//onix:TitleText', NS)
            if s_title is not None:
                series_names.append(s_title.text.strip())
        series_str = ", ".join(series_names) if series_names else "Brak serii"

        # 5. NOWE: Wydanie (Numer i typ)
        edition_number = get_text('onix:EditionNumber')
        edition_statement = get_text('onix:EditionStatement')
        full_edition = f"Wydanie {edition_number}"
        if edition_statement != "Brak":
            full_edition += f" ({edition_statement})"

        # 6. Opis
        description = "Brak opisu"
        text_content = product.find('.//onix:TextContent[onix:TextType="03"]/onix:Text', NS)
        if text_content is not None:
            raw_html = text_content.text or ""
            description = re.sub('<[^<]+?>', '', raw_html).strip()

        # 7. Okładka
        cover_url = "Brak okładki"
        for res in product.findall('.//onix:SupportingResource', NS):
            if get_text('onix:ResourceContentType', res) == "01":
                link = res.find('.//onix:ResourceLink', NS)
                if link is not None: cover_url = link.text

        # 8. Wydawca i Pozostałe
        publisher = get_text('.//onix:Publisher/onix:PublisherName')
        imprint = get_text('.//onix:Imprint/onix:ImprintName')
        pages = get_text('.//onix:Extent[onix:ExtentType="00"]/onix:ExtentValue')
        price = get_text('.//onix:Price[onix:PriceType="02"]/onix:PriceAmount')
        currency = get_text('.//onix:Price[onix:PriceType="02"]/onix:CurrencyCode')

        return {
            "Tytuł": title,
            "Autorzy": authors_str,
            "Seria": series_str,
            "Wydanie": full_edition,
            "Wydawca": publisher,
            "Imprint": imprint,
            "Liczba stron": pages,
            "ISBN-13": isbn13,
            "Cena": f"{price} {currency}" if price != "Brak" else "Brak",
            "Opis": description[:500] + "..." if len(description) > 500 else description,
            "Link do okładki": cover_url
        }
    except Exception as e:
        return None

# --- UI ---
with st.sidebar:
    st.header("🔑 Autoryzacja eLibri")
    elibri_user = st.text_input("Username (API)", value="empik")
    elibri_pass = st.text_input("Password (API)", type="password", value="sjdhg235!S")

# Zmieniono nagłówek na "Bibliotekarz"
st.title("📖 Bibliotekarz (ONIX Parser)")

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
            
            # Lista nagłówków do tabeli końcowej (dodano Serię i Wydanie)
            headers = ["Tytuł", "Autorzy", "Seria", "Wydanie", "Wydawca", "Imprint", "Liczba stron", "ISBN-13", "Cena", "Opis", "Link do okładki"]
            
            for i, row in df_in.iterrows():
                isbn = str(row[target_col]).split('.')[0]
                xml_res = get_elibri_xml(f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn}", elibri_user, elibri_pass)
                
                if xml_res == "BŁĄD_AUTH":
                    st.error("Błędne dane logowania!")
                    st.stop()
                
                book_info = parse_onix_data(xml_res) if xml_res else None
                
                entry = {"Identyfikator": isbn}
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
