import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz", page_icon="📖", layout="centered")

# --- MAPOWANIE JĘZYKÓW ---
LANG_MAP = {
    "pol": "Polski",
    "eng": "Angielski",
    "ger": "Niemiecki",
    "fre": "Francuski",
    "ita": "Włoski",
    "spa": "Hiszpański",
    "rus": "Rosyjski",
    "lat": "Łacina",
    "cze": "Czeski",
    "jpn": "Japoński",
    "chi": "Chiński"
}

# --- CACHE ---
@st.cache_data(ttl=3600)
def get_api_response(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# --- STYLE I ANIMACJA ---
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

# --- LOGIKA POBIERANIA ---
def fetch_book_data(isbn):
    isbn_clean = re.sub(r'\D', '', str(isbn))
    if not isbn_clean: return None
    
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=details"
    res = get_api_response(url)
    
    if res:
        key = f"ISBN:{isbn_clean}"
        if key in res:
            d_main = res[key].get('data', {})
            d_details = res[key].get('details', {})
            d_idents = d_details.get('identifiers', {})
            
            # Tytuł i Autorzy
            title = d_main.get('title') or d_details.get('title') or "Brak"
            authors_list = d_main.get('authors') or d_details.get('authors')
            authors = ", ".join([a.get('name', 'Nieznany') for a in authors_list]) if authors_list else "Nieznany"
            
            # Język z tłumaczeniem
            langs_raw = d_main.get('languages') or d_details.get('languages') or []
            lang_names = []
            for l in langs_raw:
                code = l.get('key', '').replace('/languages/', '') if isinstance(l, dict) else str(l).replace('/languages/', '')
                lang_names.append(LANG_MAP.get(code, code.upper())) # Tłumacz lub daj kod WIELKIMI literami
            language = ", ".join(lang_names) if lang_names else "Brak danych"

            # Funkcja pomocnicza do list
            def get_clean_list(field_name):
                data = d_main.get(field_name) or d_details.get(field_name) or []
                if isinstance(data, list) and data:
                    if isinstance(data[0], dict): return ", ".join([x.get('name', str(x)) for x in data])
                    return ", ".join([str(x) for x in data])
                return "Brak"

            # Opis
            raw_notes = d_main.get('notes') or d_details.get('notes', "")
            if isinstance(raw_notes, dict): raw_notes = raw_notes.get('value', "")
            final_notes = str(raw_notes).strip() if raw_notes else "Brak opisu w bazie"

            # Okładka
            cover_url = "Brak okładki"
            if res[key].get('thumbnail_url'):
                cover_url = res[key].get('thumbnail_url').replace("-S.jpg", "-L.jpg").replace("-M.jpg", "-L.jpg")
            elif d_details.get('covers'):
                cid = d_details.get('covers')[0]
                if cid and cid != -1: cover_url = f"https://covers.openlibrary.org/b/id/{cid}-L.jpg"

            return {
                "Tytuł": title,
                "Autorzy": authors,
                "Język": language,
                "Liczba stron": d_main.get('number_of_pages') or d_details.get('number_of_pages') or "Brak",
                "Wydawcy": get_clean_list('publishers'),
                "Data publikacji": d_main.get('publish_date') or d_details.get('publish_date') or "Brak",
                "ISBN-13": ", ".join(d_details.get('isbn_13', []) or d_idents.get('isbn_13', [])),
                "ISBN-10": ", ".join(d_details.get('isbn_10', []) or d_idents.get('isbn_10', [])),
                "Opis z bazy": final_notes,
                "Tematy": get_clean_list('subjects'),
                "Miejsca wydania": get_clean_list('publish_places'),
                "Link do okładki (L)": cover_url,
                "LCCN": ", ".join(d_details.get('lccn', []) or d_idents.get('lccn', [])),
                "OCLC": ", ".join(d_details.get('oclc_numbers', []) or d_idents.get('oclc', []))
            }
    return None

# --- UI ---
st.title("📖 Bibliotekarz")
st.subheader("Archiwum i Katalogowanie")

if 'results_df' not in st.session_state:
    st.session_state.results_df = None

uploaded_file = st.file_uploader("Załaduj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę ISBN:", df_in.columns)
    
    if st.button("Rozpocznij przeszukiwanie archiwów"):
        final_data = []
        progress_bar = st.progress(0)
        status_msg = st.empty()
        
        # Animacja
        anim_placeholder = st.empty()
        anim_placeholder.markdown('<div class="book-container"><div class="loader-book"><div class="page"></div></div></div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            isbn = row[target_col]
            status_msg.markdown(f"Katalogowanie: `{isbn}`")
            
            book_info = fetch_book_data(isbn)
            
            entry = {"Identyfikator wejściowy": isbn}
            headers = [
                "Tytuł", "Autorzy", "Język", "Liczba stron", "Wydawcy", "Data publikacji", 
                "ISBN-13", "ISBN-10", "Opis z bazy", "Tematy", "Miejsca wydania", 
                "Link do okładki (L)", "LCCN", "OCLC"
            ]
            
            for h in headers:
                if book_info:
                    entry[h] = book_info.get(h, "Brak")
                else:
                    entry[h] = "Nie odnaleziono"
            
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            time.sleep(0.05)

        anim_placeholder.empty()
        status_msg.success("Zasoby zostały skatalogowane.")
        st.session_state.results_df = pd.DataFrame(final_data)

if st.session_state.results_df is not None:
    df_res = st.session_state.results_df
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        df_res.to_excel(writer, index=False)
    
    st.download_button("📥 Pobierz Rejestr Bibliotekarza", buf.getvalue(), "rejestr_bibliotekarza.xlsx")
    st.dataframe(df_res)
