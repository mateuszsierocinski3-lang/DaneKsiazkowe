import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz", page_icon="📖", layout="centered")

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

# --- CYTATY: HRABIA MONTE CHRISTO ---
CYTATY_MONTE_CHRISTO = [
    "„Cała mądrość ludzka zawiera się w tych dwóch słowach: Czekać i pokładać nadzieję!”",
    "„Szczęście jest jak te pałace z bajek, których strzegą smoki. Trzeba walczyć, by je zdobyć.”",
    "„Wszyscy jesteśmy sprawcami własnego losu.”",
    "„Tylko ten, kto poznał smak najwyższej rozpaczy, zdolny jest odczuć największe szczęście.”",
    "„Moim zawodem jest być wolnym.”"
]

# --- GENERATOR OPISU (BEZ AI) ---
def generate_custom_description(data):
    """Tworzy opis książki na podstawie dostępnych metadanych."""
    if not data or data.get("Tytuł") == "Brak":
        return "Brak wystarczających danych do wygenerowania opisu."

    t = data.get("Tytuł")
    a = data.get("Autorzy")
    w = data.get("Wydawcy")
    d = data.get("Data publikacji")
    s = data.get("Tematy")
    p = data.get("Liczba stron")

    # Warianty rozpoczęcia
    starts = [
        f"Książka „{t}” to dzieło, którego autorem jest {a}.",
        f"„{t}” wyszła spod pióra autora: {a}.",
        f"Pozycja zatytułowana „{t}” stanowi istotną część dorobku, za którym stoi {a}."
    ]
    
    # Informacje o wydaniu
    middle = []
    if w != "Brak":
        middle.append(f"Została opublikowana przez wydawnictwo {w}")
    if d != "Brak":
        middle.append(f"w roku {d}" if w != "Brak" else f"Ukazała się w roku {d}")
    
    mid_text = " ".join(middle) + "." if middle else ""

    # Szczegóły techniczne
    tech = ""
    if p != "Brak":
        tech = f"Publikacja liczy {p} stron. "
    
    subj = ""
    if s != "Brak":
        subj = f"Tematyka oscyluje wokół zagadnień takich jak: {s}."

    return f"{random.choice(starts)} {mid_text} {tech}{subj}".strip()

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
            
            title = d_main.get('title') or d_details.get('title') or "Brak"
            authors_list = d_main.get('authors') or d_details.get('authors')
            authors = ", ".join([a.get('name', 'Nieznany') for a in authors_list]) if authors_list else "Nieznany"
            
            def get_clean_list(field_name):
                data = d_main.get(field_name) or d_details.get(field_name) or []
                if isinstance(data, list) and data:
                    if isinstance(data[0], dict): return ", ".join([x.get('name', str(x)) for x in data])
                    return ", ".join([str(x) for x in data])
                return "Brak"

            cover_url = "Brak okładki"
            if res[key].get('thumbnail_url'):
                cover_url = res[key].get('thumbnail_url').replace("-S.jpg", "-L.jpg").replace("-M.jpg", "-L.jpg")
            elif d_details.get('covers'):
                cid = d_details.get('covers')[0]
                if cid and cid != -1: cover_url = f"https://covers.openlibrary.org/b/id/{cid}-L.jpg"

            return {
                "Tytuł": title,
                "Autorzy": authors,
                "Liczba stron": d_main.get('number_of_pages') or d_details.get('number_of_pages') or "Brak",
                "Wydawcy": get_clean_list('publishers'),
                "Data publikacji": d_main.get('publish_date') or d_details.get('publish_date') or "Brak",
                "ISBN-13": ", ".join(d_details.get('isbn_13', []) or d_idents.get('isbn_13', [])),
                "ISBN-10": ", ".join(d_details.get('isbn_10', []) or d_idents.get('isbn_10', [])),
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
        
        anim_placeholder = st.empty()
        anim_placeholder.markdown('<div class="book-container"><div class="loader-book"><div class="page"></div></div></div>', unsafe_allow_html=True)
        
        quote_placeholder = st.empty()
        quote_placeholder.markdown(f'<div class="quote-style">{random.choice(CYTATY_MONTE_CHRISTO)}<br><small>— Aleksander Dumas</small></div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            isbn = row[target_col]
            status_msg.markdown(f"Katalogowanie: `{isbn}`")
            
            book_info = fetch_book_data(isbn)
            
            entry = {"Identyfikator wejściowy": isbn}
            headers = [
                "Tytuł", "Autorzy", "Liczba stron", "Wydawcy", "Data publikacji", 
                "ISBN-13", "ISBN-10", "Tematy", "Miejsca wydania", 
                "Link do okładki (L)", "LCCN", "OCLC"
            ]
            
            for h in headers:
                if book_info:
                    entry[h] = book_info.get(h, "Brak")
                else:
                    entry[h] = "Nie odnaleziono"
            
            # DODANIE GENEROWANEGO OPISU
            entry["Wygenerowany Opis"] = generate_custom_description(book_info)
            
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            time.sleep(0.1)

        anim_placeholder.empty()
        quote_placeholder.empty()
        status_msg.success("Zasoby zostały skatalogowane.")
        st.session_state.results_df = pd.DataFrame(final_data)

if st.session_state.results_df is not None:
    df_res = st.session_state.results_df
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        df_res.to_excel(writer, index=False)
    
    st.download_button("📥 Pobierz Rejestr Bibliotekarza", buf.getvalue(), "rejestr_bibliotekarza.xlsx")
    st.dataframe(df_res)
