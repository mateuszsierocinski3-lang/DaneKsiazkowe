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
NS = {'onix': 'http://ns.editeur.org/onix/3.1/reference'}

# --- STYLE I ANIMACJA (CSS) ---
st.markdown("""
<style>
    .book-container { display: flex; justify-content: center; padding: 20px; }
    .loader-book { width: 50px; height: 35px; position: relative; border: 3px solid #2c3e50; background: white; }
    .loader-book::after { content: ''; position: absolute; left: 50%; top: 0; width: 1px; height: 100%; background: #2c3e50; }
    .page { position: absolute; right: 0; top: 0; width: 50%; height: 100%; background: #f0f0f0; transform-origin: left center; animation: flip 1.2s infinite ease-in-out; border-left: 1px solid #ccc; }
    @keyframes flip { 0% { transform: rotateY(0deg); } 80%, 100% { transform: rotateY(-180deg); } }
    .quote-style { text-align: center; font-family: 'Georgia', serif; font-style: italic; color: #2c3e50; background: #fdfcf0; padding: 20px; border-left: 5px solid #2c3e50; margin: 20px 0; }
</style>
""", unsafe_allow_html=True)

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

        title = get_text('.//onix:TitleDetail[onix:TitleType="01"]//onix:TitleText')
        authors = [get_text('onix:PersonName', c) for c in product.findall('.//onix:Contributor', NS)]
        authors_str = ", ".join([a for a in authors if a != "Brak"])

        pub_date_raw = get_text('.//onix:PublishingDate[onix:PublishingDateRole="01"]/onix:Date')
        pub_date = f"{pub_date_raw[:4]}-{pub_date_raw[4:6]}-{pub_date_raw[6:]}" if len(pub_date_raw) == 8 else pub_date_raw

        lang_code = get_text('.//onix:Language[onix:LanguageRole="01"]/onix:LanguageCode')
        categories = [get_text('onix:SubjectHeadingText', s) for s in product.findall('.//onix:Subject', NS)]
        categories_str = " | ".join([c for c in categories if c != "Brak"])

        description = "Brak opisu"
        text_node = product.find('.//onix:TextContent[onix:TextType="03"]/onix:Text', NS)
        if text_node is not None:
            raw_html = text_node.text or ""
            description = re.sub('<[^<]+?>', '', raw_html).strip()

        cover_url = "Brak okładki"
        for res in product.findall('.//onix:SupportingResource', NS):
            if get_text('onix:ResourceContentType', res) == "01":
                link = res.find('.//onix:ResourceLink', NS)
                if link is not None: cover_url = link.text

        return {
            "Tytuł": title, "Autorzy": authors_str, "Data premiery": pub_date,
            "Język": lang_code, "Kategorie": categories_str,
            "Wydawca": get_text('.//onix:Publisher/onix:PublisherName'),
            "Liczba stron": get_text('.//onix:Extent[onix:ExtentType="00"]/onix:ExtentValue'),
            "ISBN-13": get_text('.//onix:ProductIdentifier[onix:ProductIDType="15"]/onix:IDValue'),
            "Cena": get_text('.//onix:Price[onix:PriceType="02"]/onix:PriceAmount'),
            "Opis": description, "Link do okładki": cover_url
        }
    except Exception:
        return None

# --- CYTATY ---
CYTATY_MONTE_CHRISTO = [
    "„Cała mądrość ludzka zawiera się w tych dwóch słowach: Czekać i pokładać nadzieję!”",
    "„Szczęście jest jak te pałace z bajek, których strzegą smoki. Trzeba walczyć, by je zdobyć.”",
    "„Wszyscy jesteśmy sprawcami własnego losu.”",
    "„Tylko ten, kto poznał smak najwyższej rozpaczy, zdolny jest odczuć największe szczęście.”",
    "„Moim zawodem jest być wolnym.”"
]

# --- UI SIDEBAR ---
with st.sidebar:
    st.header("🔑 Autoryzacja eLibri")
    elibri_user = st.text_input("Username (API)", value="empik")
    elibri_pass = st.text_input("Password (API)", type="password", value="sjdhg235!S")

# --- UI MAIN ---
st.title("📖 Bibliotekarz eLibri ONIX")

if 'results_df' not in st.session_state:
    st.session_state.results_df = None

uploaded_file = st.file_uploader("Załaduj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę z ISBN:", df_in.columns)
    
    if st.button("Rozpocznij katalogowanie"):
        final_data = []
        progress_bar = st.progress(0)
        status_msg = st.empty()
        
        # Miejsce na animację i cytat
        anim_placeholder = st.empty()
        quote_placeholder = st.empty()
        
        anim_placeholder.markdown('<div class="book-container"><div class="loader-book"><div class="page"></div></div></div>', unsafe_allow_html=True)
        quote_placeholder.markdown(f'<div class="quote-style">{random.choice(CYTATY_MONTE_CHRISTO)}<br><small>— Aleksander Dumas</small></div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            isbn_raw = str(row[target_col]).split('.')[0].strip()
            status_msg.text(f"Przetwarzanie: {isbn_raw}")
            
            xml_content = get_elibri_xml(f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn_raw}", elibri_user, elibri_pass)
            book_info = parse_onix_data(xml_content) if xml_content and xml_content != "BŁĄD_AUTH" else None
            
            entry = {"Identyfikator": isbn_raw}
            headers = ["Tytuł", "Autorzy", "Data premiery", "Język", "Kategorie", "Wydawca", "Liczba stron", "ISBN-13", "Cena", "Opis", "Link do okładki"]
            
            for h in headers:
                entry[h] = book_info.get(h, "Brak") if book_info else "Nie znaleziono"
            
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            time.sleep(0.05)

        anim_placeholder.empty()
        quote_placeholder.empty()
        st.session_state.results_df = pd.DataFrame(final_data)
        st.success("Katalogowanie zakończone!")

if st.session_state.results_df is not None:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    st.download_button("📥 Pobierz Rejestr Excel", buf.getvalue(), "rejestr_elibri.xlsx")
    st.dataframe(st.session_state.results_df)
