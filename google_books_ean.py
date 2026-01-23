import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA I ESTETYKA ---
st.set_page_config(page_title="ISBN Master Ultimate", page_icon="📚")

CYTATY_HRABIEGO = [
    "Czekać i mieć nadzieję.",
    "Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!",
    "Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają.",
    "Trzeba zaznać smaku śmierci, by wiedzieć, jak dobrze jest żyć.",
    "Litość jest uczuciem, które najbardziej upodabnia człowieka do Boga."
]

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

# --- LOGIKA WARIANTÓW EAN ---

def get_ean_variants(raw_val):
    """Tworzy listę unikalnych wariantów kodu do sprawdzenia."""
    s = str(raw_val).strip()
    # Naprawa formatu naukowego Excela
    if 'E' in s.upper() or '.' in s:
        try: s = "{:.0f}".format(float(raw_val))
        except: pass
    
    clean = re.sub(r'\D', '', s)
    if not clean: return []

    variants = set()
    variants.add(clean)                    # Oryginał
    variants.add(clean.lstrip('0'))         # Bez zer wiodących
    if len(clean) == 12:                   # Jeśli brakuje jednego zera
        variants.add("0" + clean)
    if len(clean) >= 10:                   # Wariant ISBN-10
        variants.add(clean[-10:])
    
    return list(filter(None, variants))

# --- SILNIK POBIERANIA ---

def fetch_from_all_sources(ean_list):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    
    for ean in ean_list:
        # 1. GOOGLE BOOKS (Najpierw próba ogólna, potem isbn:)
        for q in [ean, f"isbn:{ean}"]:
            try:
                res = requests.get(f"https://www.googleapis.com/books/v1/volumes?q={q}", timeout=5)
                if res.status_code == 200:
                    items = res.json().get('items', [])
                    if items:
                        v = items[0]['volumeInfo']
                        ids = v.get('industryIdentifiers', [])
                        return {
                            "ISBN-13": next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), ean),
                            "ISBN-10": next((i['identifier'] for i in ids if i['type'] == 'ISBN_10'), ""),
                            "Tytuł": v.get('title', ""),
                            "Autor": ", ".join(v.get('authors', [])),
                            "Wydawca": v.get('publisher', ""),
                            "Opis": v.get('description', "Brak opisu"),
                            "Opublikowane": v.get('publishedDate', ""),
                            "Liczba stron": v.get('pageCount', ""),
                            "Link do okładki": v.get('imageLinks', {}).get('thumbnail', "").replace("http://", "https://"),
                            "Źródło": "Google"
                        }
            except: pass

        # 2. WOLNE LEKTURY
        try:
            res = requests.get(f"https://wolnelektury.pl/api/books/?isbn={ean}", timeout=5)
            if res.status_code == 200:
                wl_data = res.json()
                if wl_data:
                    b = wl_data[0]
                    return {"Tytuł": b.get('title'), "Autor": b.get('author'), "Wydawca": "Wolne Lektury", "Link do okładki": b.get('simple_thumb'), "Źródło": "Wolne Lektury"}
        except: pass

        # 3. BIBLIOTEKA NARODOWA (Pełny rekord)
        try:
            res = requests.get(f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={ean}", timeout=5)
            if res.status_code == 200:
                bibs = res.json().get('bibs', [])
                if bibs:
                    b = bibs[0]
                    return {"Tytuł": b.get('title'), "Autor": b.get('author'), "Wydawca": b.get('publisher'), "Opublikowane": b.get('publicationYear'), "Źródło": "BN"}
        except: pass

        # 4. OPEN LIBRARY
        try:
            res = requests.get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{ean}&format=json&jscmd=data", timeout=5)
            if res.status_code == 200 and f"ISBN:{ean}" in res.json():
                ol = res.json()[f"ISBN:{ean}"]
                return {"Tytuł": ol.get('title'), "Autor": ", ".join([a['name'] for a in ol.get('authors', [])]), "Wydawca": ", ".join([p['name'] for p in ol.get('publishers', [])]), "Źródło": "Open Library"}
        except: pass

    return None

# --- INTERFEJS ---

st.title("📚 ISBN Multi-Variant Scraper")
file = st.file_uploader("Wgraj Excel z numerami EAN", type=["xlsx"])

if file:
    df_in = pd.read_excel(file)
    col = st.selectbox("Kolumna z EAN:", df_in.columns)
    
    if st.button("🚀 Rozpocznij głębokie skanowanie"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        anim = st.empty()
        
        anim.markdown(f"""
            <div class="book-container">
                <div class="book"><div class="page"></div><div class="page"></div><div class="page"></div></div>
                <div class="quote-box">"{random.choice(CYTATY_HRABIEGO)}"<br><small>— Hrabia Monte Christo</small></div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            raw_ean = row[col]
            variants = get_ean_variants(raw_ean)
            status.text(f"Sprawdzam warianty dla: {raw_ean}")
            
            data = fetch_from_all_sources(variants)
            
            entry = {"EAN z pliku": raw_ean}
            schema = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            for s in schema:
                entry[s] = data.get(s, "Nie znaleziono") if data else "Nie znaleziono"
            
            results.append(entry)
            bar.progress((i+1)/len(df_in))
            time.sleep(0.3)

        anim.empty()
        status.success("✅ Skończone! Wszystkie warianty sprawdzone.")
        
        df_res = pd.DataFrame(results)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        st.download_button("📥 Pobierz wynik", buf.getvalue(), "wyniki_isbn_deep.xlsx")
        st.dataframe(df_res)
