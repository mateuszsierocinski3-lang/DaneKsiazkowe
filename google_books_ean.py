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
# Standard ONIX 3.1 używany przez eLibri
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

        # 1. Tytuł i Autorzy
        title = get_text('.//onix:TitleDetail[onix:TitleType="01"]//onix:TitleText')
        authors = [get_text('onix:PersonName', c) for c in product.findall('.//onix:Contributor', NS)]
        authors_str = ", ".join([a for a in authors if a != "Brak"])

        # 2. Data premiery (z formatowaniem)
        pub_date_raw = get_text('.//onix:PublishingDate[onix:PublishingDateRole="01"]/onix:Date')
        if pub_date_raw != "Brak" and len(pub_date_raw) == 8:
            pub_date = f"{pub_date_raw[:4]}-{pub_date_raw[4:6]}-{pub_date_raw[6:]}"
        else:
            pub_date = pub_date_raw

        # 3. Język i Kategorie
        lang_code = get_text('.//onix:Language[onix:LanguageRole="01"]/onix:LanguageCode')
        categories = []
        for subject in product.findall('.//onix:Subject', NS):
            cat_text = get_text('onix:SubjectHeadingText', subject)
            if cat_text != "Brak": categories.append(cat_text)
        categories_str = " | ".join(categories) if categories else "Brak"

        # 4. Opis (czyszczenie HTML z CDATA)
        description = "Brak opisu"
        text_node = product.find('.//onix:TextContent[onix:TextType="03"]/onix:Text', NS)
        if text_node is not None:
            raw_html = text_node.text or ""
            description = re.sub('<[^<]+?>', '', raw_html).strip()

        # 5. Okładka i pozostałe
        cover_url = "Brak okładki"
        for res in product.findall('.//onix:SupportingResource', NS):
            if get_text('onix:ResourceContentType', res) == "01":
                link = res.find('.//onix:ResourceLink', NS)
                if link is not None: cover_url = link.text

        return {
            "Tytuł": title,
            "Autorzy": authors_str,
            "Data premiery": pub_date,
            "Język": lang_code,
            "Kategorie": categories_str,
            "Wydawca": get_text('.//onix:Publisher/onix:PublisherName'),
            "Liczba stron": get_text('.//onix:Extent[onix:ExtentType="00"]/onix:ExtentValue'),
            "ISBN-13": get_text('.//onix:ProductIdentifier[onix:ProductIDType="15"]/onix:IDValue'),
            "Cena": get_text('.//onix:Price[onix:PriceType="02"]/onix:PriceAmount'),
            "Opis": description,
            "Link do okładki": cover_url
        }
    except Exception:
        return None

# --- CYTATY ---
CYTATY = [
    "„Cała mądrość ludzka zawiera się w tych dwóch słowach: Czekać i pokładać nadzieję!”",
    "„Wszyscy jesteśmy sprawcami własnego losu.”"
]

# --- UI SIDEBAR (Twoje dane logowania) ---
with st.sidebar:
    st.header("🔑 Autoryzacja eLibri")
    # Wpisane na stałe zgodnie z prośbą
    elibri_user = st.text_input("Username (API)", value="empik")
    elibri_pass = st.text_input("Password (API)", type="password", value="sjdhg235!S")
    st.info("Dane autoryzacyjne są gotowe.")

# --- UI MAIN ---
st.title("📖 Bibliotekarz eLibri ONIX")
st.subheader("Automatyczne katalogowanie zasobów z bazy eLibri")

if 'results_df' not in st.session_state:
    st.session_state.results_df = None

uploaded_file = st.file_uploader("Załaduj plik Excel (kolumna z ISBN)", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę z numerami ISBN:", df_in.columns)
    
    if st.button("Rozpocznij pobieranie danych z eLibri"):
        if not elibri_user or not elibri_pass:
            st.error("Brak danych logowania w panelu bocznym!")
        else:
            final_data = []
            progress_bar = st.progress(0)
            status_msg = st.empty()
            
            # Losowy cytat na czas oczekiwania
            st.info(random.choice(CYTATY))

            for i, row in df_in.iterrows():
                # Czyszczenie ISBN (usuwanie .0 jeśli Excel zamienił na float)
                isbn_raw = str(row[target_col]).split('.')[0].strip()
                status_msg.text(f"Pobieranie: {isbn_raw} ({i+1}/{len(df_in)})")
                
                url = f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn_raw}"
                xml_content = get_elibri_xml(url, elibri_user, elibri_pass)
                
                if xml_content == "BŁĄD_AUTH":
                    st.error("Błąd autoryzacji eLibri! Sprawdź login i hasło.")
                    st.stop()
                
                book_info = parse_onix_data(xml_content) if xml_content else None
                
                entry = {"Identyfikator wejściowy": isbn_raw}
                headers = [
                    "Tytuł", "Autorzy", "Data premiery", "Język", "Kategorie", 
                    "Wydawca", "Liczba stron", "ISBN-13", "Cena", "Opis", "Link do okładki"
                ]
                
                for h in headers:
                    entry[h] = book_info.get(h, "Nie znaleziono") if book_info else "Brak danych"
                
                final_data.append(entry)
                progress_bar.progress((i + 1) / len(df_in))
                time.sleep(0.1)

            st.session_state.results_df = pd.DataFrame(final_data)
            status_msg.success("Zakończono pobieranie danych!")

if st.session_state.results_df is not None:
    st.divider()
    df_res = st.session_state.results_df
    
    # Przycisk pobierania
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        df_res.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Pobierz wyniki (Excel)",
        data=buf.getvalue(),
        file_name="katalog_elibri.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.dataframe(df_res)
