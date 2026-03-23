import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import time
import re
import io
import xml.etree.ElementTree as ET

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz Pro", page_icon="📖", layout="wide")

# --- GOOGLE ANALYTICS (Wersja z poprawionym zasięgiem) ---
def inject_ga(tag_id):
    """Wstrzykuje kod Google Analytics z dostępem do okna nadrzędnego."""
    ga_code = f"""
        <script async src="https://www.googletagmanager.com/gtag/js?id={tag_id}"></script>
        <script>
            window.parent.dataLayer = window.parent.dataLayer || [];
            function gtag(){{window.parent.dataLayer.push(arguments);}}
            gtag('js', new Date());
            gtag('config', '{tag_id}');
        </script>
    """
    # Renderowanie komponentu HTML o wysokości 0, aby był niewidoczny
    components.html(ga_code, height=0)

def track_event(category, action, label):
    """Funkcja do śledzenia niestandardowych zdarzeń w GA4."""
    js_event = f"""
        <script>
            if(window.parent.gtag) {{
                window.parent.gtag('event', '{action}', {{
                    'event_category': '{category}',
                    'event_label': '{label}'
                }});
            }}
        </script>
    """
    components.html(js_event, height=0)

# --- INICJALIZACJA ANALITYKI ---
# Zmień poniższy ID na swój właściwy kod pomiaru
MY_GA_ID = "G-EYLDFL816H" 
inject_ga(MY_GA_ID)

# --- SŁOWNIK JĘZYKÓW ---
LANG_MAP = {
    "pol": "polski", "eng": "angielski", "ger": "niemiecki",
    "fre": "francuski", "rus": "rosyjski", "ita": "włoski",
    "spa": "hiszpański", "lat": "łacina", "cze": "czeski", "ukr": "ukraiński"
}

# --- POBIERANIE POŚWIADCZEŃ Z SECRETS ---
try:
    # Klucze pobierane z bezpiecznej sekcji Secrets w Streamlit Cloud
    ELIBRI_USER = st.secrets["elibri"]["username"]
    ELIBRI_PASS = st.secrets["elibri"]["password"]
except KeyError:
    st.error("❌ Brakuje konfiguracji Secrets! Dodaj 'elibri.username' i 'elibri.password' w ustawieniach Streamlit.")
    st.stop()

# --- FUNKCJE POMOCNICZE ---
def reverse_authors(authors_str):
    if not authors_str or authors_str in ["Nieznany", "Brak", "Błąd danych"]:
        return authors_str
    parts = authors_str.split(",") 
    reversed_parts = []
    for part in parts:
        name_atoms = part.strip().split()
        if len(name_atoms) >= 2:
            last_name = name_atoms[-1]
            first_names = " ".join(name_atoms[:-1])
            reversed_parts.append(f"{last_name} {first_names}")
        else:
            reversed_parts.append(part.strip())
    return ", ".join(reversed_parts)

def find_text(parent, path):
    node = parent.find(path)
    return node.text.strip() if node is not None and node.text else None

def format_date(date_str):
    if date_str and len(date_str) >= 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str

# --- PARSER ONIX ---
def parse_onix_data(xml_content):
    try:
        xml_content_str = xml_content.decode('utf-8') if isinstance(xml_content, bytes) else xml_content
        xml_content_str = re.sub(r'\sxmlns="[^"]+"', '', xml_content_str, count=1)
        root = ET.fromstring(xml_content_str)
        product = root if root.tag == 'Product' else root.find('.//Product')
        if product is None: return None

        isbn13 = find_text(product, './/ProductIdentifier[ProductIDType="15"]/IDValue') or "Brak"
        title = find_text(product, './/TitleDetail[TitleType="01"]//TitleText') or "Brak tytułu"
        
        authors = []
        for contrib in product.findall('.//Contributor'):
            name = find_text(contrib, 'PersonName')
            if name: authors.append(name)
        authors_str = ", ".join(authors) if authors else "Nieznany"

        desc_detail = product.find('DescriptiveDetail')
        oprawa = "Nieznana"
        language_display = "Brak"
        if desc_detail is not None:
            p_form = find_text(desc_detail, 'ProductForm')
            p_detail = find_text(desc_detail, 'ProductFormDetail')
            if p_form == "BC":
                oprawa = "Miękka ze skrzydełkami" if p_detail == "B504" else "Miękka"
            elif p_form == "BB":
                oprawa = "Twarda"
            
            lang_node = desc_detail.find('.//Language[LanguageRole="01"]/LanguageCode')
            if lang_node is not None:
                l_code = lang_node.text.strip().lower()
                language_display = LANG_MAP.get(l_code, l_code.upper())

        publisher = find_text(product, './/Publisher/PublisherName') or "Brak"

        return {
            "Tytuł": title,
            "Autorzy": authors_str,
            "Autorzy (Nazwisko Imię)": reverse_authors(authors_str),
            "Oprawa": oprawa,
            "Język": language_display,
            "Wydawca": publisher,
            "ISBN-13": isbn13
        }
    except Exception:
        return None

# --- UI STREAMLIT ---
st.title("📖 Bibliotekarz ONIX (eLibri)")
st.info("Aplikacja korzysta z Google Analytics do monitorowania ruchu.")

uploaded_file = st.file_uploader("Załaduj plik Excel z kolumną ISBN", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę z numerami ISBN:", df_in.columns)
    
    if st.button("Pobierz dane z API"):
        # Rejestracja zdarzenia w GA4
        track_event("UserEngagement", "API_Request", f"Items_{len(df_in)}")
        
        final_data = []
        progress_bar = st.progress(0)
        
        headers = ["Tytuł", "Autorzy", "Autorzy (Nazwisko Imię)", "Oprawa", "Język", "Wydawca", "ISBN-13"]
        
        for i, row in df_in.iterrows():
            isbn_raw = str(row[target_col]).split('.')[0].strip()
            url = f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn_raw}"
            try:
                # Autoryzacja pobierana z bezpiecznych zmiennych
                r = requests.get(url, auth=(ELIBRI_USER, ELIBRI_PASS), timeout=10)
                xml_res = r.content if r.status_code == 200 else None
            except:
                xml_res = None
            
            book_info = parse_onix_data(xml_res) if xml_res else None
            entry = {"Identyfikator": isbn_raw}
            for h in headers:
                entry[h] = book_info.get(h, "Błąd/Brak") if book_info else "Nie znaleziono"
            
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            time.sleep(0.05)

        st.session_state.results_df = pd.DataFrame(final_data)
        st.success("Dane zostały pobrane!")

if 'results_df' in st.session_state:
    st.dataframe(st.session_state.results_df)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    
    if st.download_button("📥 Pobierz Excel", buf.getvalue(), "rejestr_elibri.xlsx"):
        # Śledzenie pobrania pliku
        track_event("UserEngagement", "File_Download", "Excel_Success")
