import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="ISBN Ultimate Multi-Scraper", page_icon="📚")

CYTATY_HRABIEGO = [
    "Czekać i mieć nadzieję.",
    "Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!",
    "Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają.",
    "Wszystkie nieszczęścia ludzi płyną z nadziei.",
    "Trzeba zaznać smaku śmierci, by wiedzieć, jak dobrze jest żyć.",
    "Litość jest uczuciem, które najbardziej upodabnia człowieka do Boga."
]

# --- STYLIZACJA CSS (Książka i Cytat) ---
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

# --- FUNKCJE POBIERANIA ---

def clean_ean(ean):
    if pd.isna(ean): return ""
    s = str(ean).strip()
    if 'E' in s.upper() or '.' in s:
        try: s = "{:.0f}".format(float(ean))
        except: pass
    return re.sub(r'\D', '', s)

def get_google(ean):
    for q in [f"isbn:{ean}", ean]:
        try:
            url = f"https://www.googleapis.com/books/v1/volumes?q={q}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200 and 'items' in r.json():
                v = r.json()['items'][0]['volumeInfo']
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
    return None

def get_wolne_lektury(ean):
    """Odpytuje API WolneLektury.pl"""
    try:
        # Wolne Lektury nie szukają bezpośrednio po ISBN w głównym API, 
        # ale sprawdzamy ich bazę przez wyszukiwarkę ogólną.
        url = f"https://wolnelektury.pl/api/books/?isbn={ean}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            results = r.json()
            if results:
                b = results[0]
                return {
                    "Tytuł": b.get('title', ""),
                    "Autor": b.get('author', ""),
                    "Wydawca": "Wolne Lektury",
                    "Link do okładki": b.get('simple_thumb', ""),
                    "Źródło": "Wolne Lektury"
                }
    except: pass
    return None

def get_bn(ean):
    """Pełne odpytanie Biblioteki Narodowej."""
    try:
        url = f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={ean}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            bibs = r.json().get('bibs', [])
            if bibs:
                b = bibs[0]
                return {
                    "Tytuł": b.get('title', ""),
                    "Autor": b.get('author', ""),
                    "Wydawca": b.get('publisher', ""),
                    "Opublikowane": b.get('publicationYear', ""),
                    "Opis": "Rekord w BN",
                    "Źródło": "BN"
                }
    except: pass
    return None

def get_open_library(ean):
    try:
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{ean}&format=json&jscmd=data"
        r = requests.get(url, timeout=5)
        if r.status_code == 200 and f"ISBN:{ean}" in r.json():
            ol = r.json()[f"ISBN:{ean}"]
            return {
                "Tytuł": ol.get('title', ""),
                "Autor": ", ".join([a['name'] for a in ol.get('authors', [])]),
                "Wydawca": ", ".join([p['name'] for p in ol.get('publishers', [])]),
                "Link do okładki": ol.get('cover', {}).get('large', ""),
                "Źródło": "Open Library"
            }
    except: pass
    return None

# --- UI ---
st.title("📚 ISBN Multi-Scraper Pro")
file = st.file_uploader("Wgraj plik Excel (.xlsx)", type=["xlsx"])

if file:
    df_in = pd.read_excel(file)
    col = st.selectbox("Wybierz kolumnę z EAN/ISBN:", df_in.columns)
    
    if st.button("🚀 Rozpocznij mielenie bazy"):
        final_results = []
        prog = st.progress(0)
        status = st.empty()
        anim = st.empty()
        
        # Start animacji
        anim.markdown(f"""
            <div class="book-container">
                <div class="book"><div class="page"></div><div class="page"></div><div class="page"></div></div>
                <div class="quote-box">"{random.choice(CYTATY_HRABIEGO)}"<br><small>— Hrabia Monte Christo</small></div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            ean = clean_ean(row[col])
            status.text(f"Przeszukuję bazy dla: {ean}...")
            
            # Łańcuch źródeł
            res = get_google(ean)
            if not res: res = get_wolne_lektury(ean)
            if not res: res = get_open_library(ean)
            if not res: res = get_bn(ean)

            # Mapowanie kolumn (zachowanie Twojej struktury)
            entry = {"EAN z pliku": ean}
            schema = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            
            for s in schema:
                if res and s in res:
                    entry[s] = res[s]
                else:
                    entry[s] = "Nie znaleziono"
            
            final_results.append(entry)
            prog.progress((i+1)/len(df_in))
            time.sleep(0.4) # Stabilność

        anim.empty()
        status.success("✅ Przetwarzanie ukończone!")
        
        df_final = pd.DataFrame(final_results)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, index=False)
            
        st.download_button("📥 Pobierz wynikowy Excel", buf.getvalue(), "wynik_multibaza.xlsx")
        st.dataframe(df_final)
