import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="ISBN Ultimate Scraper", page_icon="📚")

CYTATY_HRABIEGO = [
    "Czekać i mieć nadzieję.",
    "Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!",
    "Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają.",
    "Trzeba zaznać smaku śmierci, by wiedzieć, jak dobrze jest żyć.",
    "Jestem tym, kim jestem: narzędziem w rękach Boga."
]

# --- STYLIZACJA CSS ---
st.markdown("""
<style>
    .book-container { display: flex; flex-direction: column; align-items: center; padding: 20px; }
    .book { width: 60px; height: 45px; position: relative; perspective: 150px; margin-bottom: 20px; }
    .page { width: 30px; height: 45px; background: white; border: 2px solid #333; position: absolute; right: 0; transform-origin: left; animation: flip 1.2s infinite linear; border-radius: 0 2px 2px 0; }
    .page:nth-child(2) { animation-delay: 0.4s; }
    .page:nth-child(3) { animation-delay: 0.8s; }
    @keyframes flip { 0% { transform: rotateY(0deg); } 100% { transform: rotateY(-180deg); } }
    .book::before { content: ''; position: absolute; width: 30px; height: 45px; background: #eee; border: 2px solid #333; left: 0; border-radius: 2px 0 0 2px; }
    .quote-box { text-align: center; font-family: 'Georgia', serif; font-style: italic; color: #555; background: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #0e1117; max-width: 500px; }
</style>
""", unsafe_allow_html=True)

# --- FUNKCJE POBIERANIA DANYCH ---

def clean_ean(ean):
    if pd.isna(ean): return ""
    s = str(ean).strip()
    if 'E' in s.upper() or '.' in s:
        try: s = "{:.0f}".format(float(ean))
        except: pass
    return re.sub(r'\D', '', s)

def get_google_books(ean):
    """Nadrzędne wyszukiwanie w Google Books."""
    # Próbujemy zapytania po ISBN oraz ogólnego
    for query in [f"isbn:{ean}", ean]:
        try:
            url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=1"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if 'items' in data:
                    item = data['items'][0]['volumeInfo']
                    ids = item.get('industryIdentifiers', [])
                    img = item.get('imageLinks', {})
                    return {
                        "ISBN-13": next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), ean),
                        "ISBN-10": next((i['identifier'] for i in ids if i['type'] == 'ISBN_10'), ""),
                        "Tytuł": item.get('title', ""),
                        "Autor": ", ".join(item.get('authors', [])),
                        "Wydawca": item.get('publisher', ""),
                        "Opis": item.get('description', ""),
                        "Opublikowane": item.get('publishedDate', ""),
                        "Liczba stron": item.get('pageCount', ""),
                        "Link do okładki": (img.get('thumbnail') or "").replace("http://", "https://"),
                        "Źródło": "Google"
                    }
        except: continue
    return None

def get_open_library(ean):
    """Baza wspierająca: Open Library."""
    try:
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{ean}&format=json&jscmd=data"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            key = f"ISBN:{ean}"
            if key in data:
                b = data[key]
                return {
                    "Tytuł": b.get('title', ""),
                    "Autor": ", ".join([a['name'] for a in b.get('authors', [])]),
                    "Wydawca": ", ".join([p['name'] for p in b.get('publishers', [])]),
                    "Link do okładki": b.get('cover', {}).get('large', ""),
                    "Źródło": "Open Library"
                }
    except: pass
    return None

def get_bn_publisher(ean):
    """Gwarant wydawcy: Biblioteka Narodowa."""
    try:
        url = f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={ean}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            bibs = res.json().get('bibs', [])
            if bibs: return bibs[0].get('publisher', "").strip()
    except: pass
    return None

# --- GŁÓWNA LOGIKA ---

st.title("📚 ISBN Multibaza Scraper")
uploaded_file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    col = st.selectbox("Wybierz kolumnę EAN:", df_in.columns)
    
    if st.button("🚀 Rozpocznij weryfikację"):
        results = []
        progress = st.progress(0)
        status = st.empty()
        anim = st.empty()
        
        anim.markdown(f"""
            <div class="book-container">
                <div class="book"><div class="page"></div><div class="page"></div><div class="page"></div></div>
                <div class="quote-box">"{random.choice(CYTATY_HRABIEGO)}"<br><small>— Hrabia Monte Christo</small></div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            ean = clean_ean(row[col])
            status.text(f"Szukam: {ean}...")
            
            # 1. Google (Nadrzędne)
            data = get_google_books(ean)
            
            # 2. Open Library (Jeśli Google nie ma)
            if not data:
                ol = get_open_library(ean)
                if ol:
                    data = {k: "Nie znaleziono" for k in ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki"]}
                    data.update(ol)
            
            # 3. BN (Uzupełnienie wydawcy jeśli nadal brak)
            if not data or not data.get("Wydawca"):
                bn_pub = get_bn_publisher(ean)
                if bn_pub:
                    if not data:
                        data = {k: "Nie znaleziono" for k in ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki"]}
                        data["Wydawca"] = bn_pub
                        data["Źródło"] = "BN"
                    else:
                        data["Wydawca"] = bn_pub

            # Budowa wiersza końcowego
            entry = {"EAN z pliku": ean}
            cols_order = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            for c in cols_order:
                entry[c] = data.get(c, "Nie znaleziono") if data else "Nie znaleziono"
            
            results.append(entry)
            progress.progress((i + 1) / len(df_in))
            time.sleep(0.3) # Ważne dla stabilności Google

        anim.empty()
        status.success("✅ Gotowe!")
        
        df_res = pd.DataFrame(results)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.download_button("📥 Pobierz wynikowy Excel", buf.getvalue(), "wynik_isbn.xlsx")
        st.dataframe(df_res)
