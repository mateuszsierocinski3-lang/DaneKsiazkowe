import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="ISBN Ultimate Scraper", page_icon="📚")

# --- LISTA CYTATÓW ---
CYTATY_HRABIEGO = [
    "Czekać i mieć nadzieję.",
    "Na tym świecie nie ma ani szczęścia, ani nieszczęścia, jest tylko porównanie jednego stanu z drugim.",
    "Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!",
    "Trzeba było nieszczęścia, by wydobyć na jaw głębie mego ducha.",
    "Jestem tym, kim jestem: narzędziem w rękach Boga.",
    "Ten, kto nigdy nie pragnął umrzeć, nie wie, jak słodko jest żyć.",
    "Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają."
]

# --- STYLIZACJA CSS (Animacja i Cytat) ---
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

# --- FUNKCJE LOGICZNE ---

def clean_ean(ean):
    if pd.isna(ean): return ""
    s = str(ean).strip()
    if 'E' in s.upper() or '.' in s:
        try: s = "{:.0f}".format(float(ean))
        except: pass
    return re.sub(r'\D', '', s)

def fetch_book_data(ean):
    """Przeszukuje Google, Open Library i BN."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    
    # 1. GOOGLE BOOKS (2 próby: isbn oraz ogólna)
    for q in [f"isbn:{ean}", ean]:
        try:
            url = f"https://www.googleapis.com/books/v1/volumes?q={q}"
            resp = requests.get(url, headers=headers, timeout=7)
            if resp.status_code == 200:
                items = resp.json().get('items', [])
                if items:
                    v = items[0]['volumeInfo']
                    ids = v.get('industryIdentifiers', [])
                    return {
                        "ISBN-13": next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), ean),
                        "ISBN-10": next((i['identifier'] for i in ids if i['type'] == 'ISBN_10'), ""),
                        "Tytuł": v.get('title', ""),
                        "Autor": ", ".join(v.get('authors', [])),
                        "Wydawca": v.get('publisher', ""),
                        "Opis": v.get('description', ""),
                        "Opublikowane": v.get('publishedDate', ""),
                        "Liczba stron": v.get('pageCount', ""),
                        "Link do okładki": v.get('imageLinks', {}).get('thumbnail', "").replace("http://", "https://"),
                        "Źródło": "Google"
                    }
        except: pass

    # 2. OPEN LIBRARY
    try:
        ol_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{ean}&format=json&jscmd=data"
        resp = requests.get(ol_url, timeout=5)
        if resp.status_code == 200 and f"ISBN:{ean}" in resp.json():
            ol = resp.json()[f"ISBN:{ean}"]
            return {
                "ISBN-13": ean, "ISBN-10": "",
                "Tytuł": ol.get('title', ""),
                "Autor": ", ".join([a['name'] for a in ol.get('authors', [])]),
                "Wydawca": ", ".join([p['name'] for p in ol.get('publishers', [])]),
                "Opis": "Brak opisu (OpenLibrary)", "Opublikowane": ol.get('publish_date', ""),
                "Liczba stron": ol.get('number_of_pages', ""),
                "Link do okładki": ol.get('cover', {}).get('large', ""), "Źródło": "Open Library"
            }
    except: pass

    # 3. BIBLIOTEKA NARODOWA
    try:
        bn_url = f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={ean}"
        resp = requests.get(bn_url, timeout=5)
        if resp.status_code == 200:
            bibs = resp.json().get('bibs', [])
            if bibs:
                return {
                    "ISBN-13": ean, "ISBN-10": "",
                    "Tytuł": bibs[0].get('title', ""), "Autor": bibs[0].get('author', ""),
                    "Wydawca": bibs[0].get('publisher', ""), "Opis": "Brak (BN)",
                    "Opublikowane": bibs[0].get('publicationYear', ""), "Liczba stron": "",
                    "Link do okładki": "", "Źródło": "BN"
                }
    except: pass

    return None

# --- INTERFEJS ---
st.title("📚 ISBN Multibaza Scraper")
uploaded_file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    col = st.selectbox("Kolumna z EAN/ISBN:", df_in.columns)
    
    if st.button("🚀 Rozpocznij przetwarzanie"):
        results = []
        prog = st.progress(0)
        status = st.empty()
        anim_placeholder = st.empty()
        
        # WYŚWIETLENIE ANIMACJI I CYTATU
        anim_placeholder.markdown(f"""
            <div class="book-container">
                <div class="book"><div class="page"></div><div class="page"></div><div class="page"></div></div>
                <div class="quote-box">"{random.choice(CYTATY_HRABIEGO)}"<br><small>— Hrabia Monte Christo</small></div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            ean = clean_ean(row[col])
            status.text(f"Przetwarzam: {ean} ({i+1}/{len(df_in)})")
            
            data = fetch_book_data(ean)
            
            entry = {"EAN z pliku": ean}
            cols_order = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            
            for c in cols_order:
                entry[c] = data.get(c, "Nie znaleziono") if data else "Nie znaleziono"
            
            results.append(entry)
            prog.progress((i + 1) / len(df_in))
            time.sleep(0.5) # Opóźnienie anty-botowe

        anim_placeholder.empty()
        status.success("✅ Przetwarzanie zakończone!")
        
        df_res = pd.DataFrame(results)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.download_button("📥 Pobierz wynikowy Excel", buf.getvalue(), "wynik_isbn.xlsx")
        st.dataframe(df_res)
