import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz", page_icon="📖", layout="centered")

# --- CACHE DLA SZYBKOŚCI DZIAŁANIA ---
@st.cache_data(ttl=3600)
def get_api_response(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# --- CYTATY: HRABIA MONTE CHRISTO ---
CYTATY_MONTE_CHRISTO = [
    "„Cała mądrość ludzka zawiera się w tych dwóch słowach: Czekać i pokładać nadzieję!”",
    "„Szczęście jest jak te pałace z bajek, których strzegą smoki. Trzeba walczyć, by je zdobyć.”",
    "„Wszyscy jesteśmy sprawcami własnego losu.”",
    "„Tylko ten, kto poznał smak najwyższej rozpaczy, zdolny jest odczuć największe szczęście.”",
    "„Moim zawodem jest być wolnym.”",
    "„Rany, które zadajemy sobie sami, goją się najwolniej.”"
]

# --- STYLE CSS I ANIMACJA STRON ---
st.markdown("""
<style>
    /* Animacja przewracanych stron */
    .book-container {
        display: flex;
        justify-content: center;
        padding: 20px;
    }
    .loader-book {
        width: 50px;
        height: 35px;
        position: relative;
        border: 3px solid #2c3e50;
    }
    .loader-book::after {
        content: '';
        position: absolute;
        left: 50%;
        top: 0;
        width: 1px;
        height: 100%;
        background: #2c3e50;
    }
    .page {
        position: absolute;
        right: 0;
        top: 0;
        width: 50%;
        height: 100%;
        background: #ecf0f1;
        transform-origin: left center;
        animation: flip 1.5s infinite ease-in-out;
        border-left: 1px solid #bdc3c7;
    }
    @keyframes flip {
        0% { transform: rotateY(0deg); }
        80%, 100% { transform: rotateY(-180deg); }
    }

    /* Wygląd cytatu */
    .quote-style {
        text-align: center;
        font-family: 'Georgia', serif;
        font-style: italic;
        color: #2c3e50;
        background: #fdfcf0;
        padding: 20px;
        border-radius: 5px;
        border-left: 5px solid #2c3e50;
        margin: 20px 0;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- GENERATOR OPISÓW ---
def create_fallback_description(title, authors, subjects):
    if not title or title == "Brak": return "Brak wystarczających informacji w rejestrach."
    desc = f"Dzieło pt. '{title}', autorstwa {authors if authors != 'Nieznany' else 'nieokreślonego twórcy'}."
    if subjects and subjects != "Brak":
        desc += f" Treść koncentruje się na zagadnieniach z zakresu: {subjects.split(',')[0].lower()}."
    return desc + " Pozycja ta stanowi cenny wkład w literaturę przedmiotu."

# --- LOGIKA BIBLIOTEKARZA ---
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
            
            # Pobieranie opisu lub generowanie własnego
            raw_notes = d_main.get('notes') or d_details.get('notes', "")
            if isinstance(raw_notes, dict): raw_notes = raw_notes.get('value', "")
            
            if not raw_notes or len(str(raw_notes)) < 15:
                description = create_fallback_description(title, authors, subjects)
                source = "Wygenerowany autorsko"
            else:
                description = str(raw_notes).strip()
                source = "Baza Biblioteczna"

            # Okładka High-Res
            cover_url = "Brak okładki"
            if res[key].get('thumbnail_url'):
                cover_url = res[key].get('thumbnail_url').replace("-S.jpg", "-L.jpg").replace("-M.jpg", "-L.jpg")
            elif d_details.get('covers'):
                cid = d_details.get('covers')[0]
                if cid and cid != -1: cover_url = f"https://covers.openlibrary.org/b/id/{cid}-L.jpg"

            return {
                "Tytuł": title, "Autorzy": authors, "Opis": description,
                "Źródło opisu": source, "ISBN-13": ", ".join(d_details.get('isbn_13', []) or d_idents.get('isbn_13', [])),
                "ISBN-10": ", ".join(d_details.get('isbn_10', []) or d_idents.get('isbn_10', [])),
                "Wydawcy": get_clean_list('publishers'), "Data publikacji": d_main.get('publish_date') or d_details.get('publish_date'),
                "Tematy": subjects, "Link do okładki (L)": cover_url
            }
    return None

# --- INTERFEJS ---
st.title("📖 Bibliotekarz")
st.subheader("System Katalogowania Woluminów")

if 'rejestr' not in st.session_state:
    st.session_state.rejestr = None

uploaded_file = st.file_uploader("Załaduj rejestr ISBN (Excel)", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę z identyfikatorami:", df_in.columns)
    
    if st.button("Uruchom skanowanie archiwów"):
        final_data = []
        progress_bar = st.progress(0)
        status_msg = st.empty()
        
        # Animacja i Cytat
        anim_placeholder = st.empty()
        anim_placeholder.markdown('<div class="book-container"><div class="loader-book"><div class="page"></div></div></div>', unsafe_allow_html=True)
        
        quote_placeholder = st.empty()
        quote_placeholder.markdown(f'<div class="quote-style">{random.choice(CYTATY_MONTE_CHRISTO)}<br><small>— Aleksander Dumas</small></div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            isbn = row[target_col]
            status_msg.markdown(f"Analizowanie woluminu: `{isbn}`")
            
            book_info = fetch_book_data(isbn)
            
            entry = {"Identyfikator wejściowy": isbn}
            headers = ["Tytuł", "Autorzy", "Opis", "Źródło opisu", "ISBN-13", "ISBN-10", "Wydawcy", "Data publikacji", "Link do okładki (L)"]
            
            for h in headers:
                entry[h] = book_info.get(h, "Brak danych") if book_info else "Nie odnaleziono"
            
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            time.sleep(0.05) # Szybkie przetwarzanie dzięki cache

        anim_placeholder.empty()
        quote_placeholder.empty()
        status_msg.success("Katalogowanie zakończone.")
        st.session_state.rejestr = pd.DataFrame(final_data)

if st.session_state.rejestr is not None:
    df_res = st.session_state.rejestr
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_res.to_excel(writer, index=False)
    
    st.download_button("📥 Pobierz Gotowy Rejestr (Excel)", output.getvalue(), "rejestr_bibliotekarza.xlsx")
    st.dataframe(df_res)
