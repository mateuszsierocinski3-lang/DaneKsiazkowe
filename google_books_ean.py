import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA STRONY (Musi być na samym początku) ---
st.set_page_config(page_title="Bibliotekarz", page_icon="📖", layout="centered")

# --- CACHE DANYCH (To drastycznie przyspiesza powtórne wyszukiwanie) ---
@st.cache_data(ttl=3600)  # Pamięta wyniki przez godzinę
def get_api_response(url):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# --- CYTATY ---
CYTATY_LITERACKIE = [
    "„Czekać i pokładać nadzieję!” — Aleksander Dumas, Hrabia Monte Christo",
    "„Pod tą maską kryje się coś więcej niż ciało. Pod tą maską kryje się idea, a idee są kuloodporne.” — Alan Moore, V jak Vendetta",
    "„Wszyscy jesteśmy sprawcami własnego losu.” — Aleksander Dumas"
]

# --- STYLE I ANIMACJA (Zoptymalizowane pod kątem szybkości renderowania) ---
st.markdown("""
<style>
    .book { position: relative; border: 5px solid #2c3e50; width: 40px; height: 30px; margin: 10px auto; }
    .book__page { position: absolute; left: 50%; top: 0; width: 50%; height: 100%; background: #ecf0f1; transform-origin: left center; animation: flip 1.2s infinite linear; border-left: 1px solid #bdc3c7; }
    @keyframes flip { 0% { transform: rotateY(0deg); } 100% { transform: rotateY(-180deg); } }
    .quote-box { text-align: center; font-style: italic; background: #fdfcf0; padding: 15px; border-left: 5px solid #e67e22; margin: 10px 0; font-size: 0.9em; }
</style>
""", unsafe_allow_html=True)

# --- LOGIKA BIZNESOWA ---
def generate_fallback_description(title, authors, subjects):
    if not title or title == "Brak": return "Brak danych do analizy."
    desc = f"Dzieło pt. '{title}', autorstwa {authors if authors != 'Nieznany' else 'anonimowego twórcy'}."
    if subjects and subjects != "Brak":
        desc += f" Tematyka oscyluje wokół zagadnień: {subjects.split(',')[0].lower()}."
    return desc + " Pozycja ta stanowi istotne studium w swojej kategorii."

def fetch_bibliotekarz_data(isbn):
    isbn_clean = re.sub(r'\D', '', str(isbn))
    if not isbn_clean: return None
    
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=details"
    res = get_api_response(url) # Używamy cache'owanej funkcji
    
    if res:
        key = f"ISBN:{isbn_clean}"
        if key in res:
            d_main = res[key].get('data', {})
            d_details = res[key].get('details', {})
            d_idents = d_details.get('identifiers', {})
            
            title = d_main.get('title') or d_details.get('title') or "Brak"
            authors_list = d_main.get('authors') or d_details.get('authors')
            authors = ", ".join([a.get('name', 'Nieznany') for a in authors_list]) if authors_list else "Nieznany"
            
            def get_clean_list(field_name):
                data = d_main.get(field_name) or d_details.get(field_name) or []
                if isinstance(data, list) and data:
                    if isinstance(data[0], dict): return ", ".join([x.get('name', str(x)) for x in data])
                    return ", ".join([str(x) for x in data])
                return "Brak"

            subjects = get_clean_list('subjects')
            raw_notes = d_main.get('notes') or d_details.get('notes', "")
            if isinstance(raw_notes, dict): raw_notes = raw_notes.get('value', "")
            
            description = str(raw_notes).strip() if (raw_notes and len(str(raw_notes)) > 15) else generate_fallback_description(title, authors, subjects)
            source_desc = "Baza Biblioteczna" if (raw_notes and len(str(raw_notes)) > 15) else "Wygenerowany autorsko"

            cover_url = "Brak okładki"
            if res[key].get('thumbnail_url'):
                cover_url = res[key].get('thumbnail_url').replace("-S.jpg", "-L.jpg").replace("-M.jpg", "-L.jpg")
            elif d_details.get('covers'):
                cid = d_details.get('covers')[0]
                if cid and cid != -1: cover_url = f"https://covers.openlibrary.org/b/id/{cid}-L.jpg"

            return {
                "Tytuł": title, "Autorzy": authors, "Krótki Opis": description,
                "Źródło Opisu": source_desc, "ISBN-13": ", ".join(d_details.get('isbn_13', []) or d_idents.get('isbn_13', [])),
                "ISBN-10": ", ".join(d_details.get('isbn_10', []) or d_idents.get('isbn_10', [])),
                "Wydawcy": get_clean_list('publishers'), "Data publikacji": d_main.get('publish_date') or d_details.get('publish_date'),
                "Tematy": subjects, "Link do okładki (L)": cover_url
            }
    return None

# --- UI ---
st.title("📖 Bibliotekarz")

if 'results_df' not in st.session_state:
    st.session_state.results_df = None

file = st.file_uploader("Załaduj plik Excel", type=["xlsx"])

if file:
    df_in = pd.read_excel(file)
    col = st.selectbox("Kolumna ISBN:", df_in.columns)
    
    if st.button("Rozpocznij katalogowanie"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        st.markdown('<div class="book"><div class="book__page"></div><div class="book__page"></div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="quote-box">{random.choice(CYTATY_LITERACKIE)}</div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            isbn_val = row[col]
            status.text(f"Przetwarzanie: {isbn_val}")
            data = fetch_bibliotekarz_data(isbn_val)
            
            res_row = {"Identyfikator": isbn_val}
            headers = ["Tytuł", "Autorzy", "Krótki Opis", "Źródło Opisu", "ISBN-13", "ISBN-10", "Wydawcy", "Data publikacji", "Link do okładki (L)"]
            
            for h in headers:
                res_row[h] = data.get(h, "Brak") if data else "Nie znaleziono"
            
            results.append(res_row)
            bar.progress((i + 1) / len(df_in))
        
        st.session_state.results_df = pd.DataFrame(results)
        status.success("Zakończono.")

if st.session_state.results_df is not None:
    df_res = st.session_state.results_df
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        df_res.to_excel(writer, index=False)
    st.download_button("📥 Pobierz Rejestr", buf.getvalue(), "rejestr.xlsx")
    st.dataframe(df_res)
