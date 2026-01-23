import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="ISBN Master Fix", page_icon="📚")

CYTATY_HRABIEGO = [
    "Czekać i mieć nadzieję.",
    "Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!",
    "Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają.",
    "Trzeba zaznać smaku śmierci, by wiedzieć, jak dobrze jest żyć."
]

# --- STYLE ---
st.markdown("""
<style>
    .book-container { display: flex; flex-direction: column; align-items: center; padding: 20px; }
    .book { width: 60px; height: 45px; position: relative; perspective: 150px; margin-bottom: 20px; }
    .page { width: 30px; height: 45px; background: white; border: 2px solid #333; position: absolute; right: 0; transform-origin: left; animation: flip 1.2s infinite linear; border-radius: 0 2px 2px 0; }
    @keyframes flip { 0% { transform: rotateY(0deg); } 100% { transform: rotateY(-180deg); } }
    .quote-box { text-align: center; font-family: 'Georgia', serif; font-style: italic; color: #555; background: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #0e1117; }
</style>
""", unsafe_allow_html=True)

# --- LOGIKA VARIANTÓW ---
def generate_variants(ean_raw):
    s = re.sub(r'\D', '', str(ean_raw))
    if not s: return []
    variants = [s]
    if s.startswith('0'): variants.append(s[1:])
    if len(s) == 12: variants.append('0' + s)
    if len(s) >= 10: variants.append(s[-10:])
    return list(dict.fromkeys(variants))

# --- POBIERANIE DANYCH ---
def get_book_info(variants):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    
    for v in variants:
        # 1. GOOGLE
        try:
            url = f"https://www.googleapis.com/books/v1/volumes?q={v}"
            r = requests.get(url, headers=headers, timeout=5).json()
            if 'items' in r:
                info = r['items'][0]['volumeInfo']
                ids = info.get('industryIdentifiers', [])
                return {
                    "ISBN-13": next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), v),
                    "ISBN-10": next((i['identifier'] for i in ids if i['type'] == 'ISBN_10'), ""),
                    "Tytuł": info.get('title', ""),
                    "Autor": ", ".join(info.get('authors', [])),
                    "Wydawca": info.get('publisher', ""),
                    "Opis": info.get('description', ""),
                    "Opublikowane": info.get('publishedDate', ""),
                    "Liczba stron": info.get('pageCount', ""),
                    "Link do okładki": info.get('imageLinks', {}).get('thumbnail', "").replace("http://", "https://"),
                    "Źródło": "Google"
                }
        except: pass

        # 2. WOLNE LEKTURY
        try:
            r = requests.get(f"https://wolnelektury.pl/api/books/?isbn={v}", timeout=5).json()
            if r:
                return {"Tytuł": r[0].get('title'), "Autor": r[0].get('author'), "Wydawca": "Wolne Lektury", "Link do okładki": r[0].get('simple_thumb'), "Źródło": "Wolne Lektury"}
        except: pass

        # 3. BN
        try:
            r = requests.get(f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={v}", timeout=5).json()
            if r.get('bibs'):
                b = r['bibs'][0]
                return {"Tytuł": b.get('title'), "Autor": b.get('author'), "Wydawca": b.get('publisher'), "Źródło": "BN"}
        except: pass
    return None

# --- APLIKACJA ---
st.title("📚 ISBN Multi-Scanner Fix")
uploaded_file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    ean_col = st.selectbox("Kolumna EAN:", df_in.columns)
    
    if st.button("🚀 Rozpocznij"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        anim = st.empty()
        
        anim.markdown(f'<div class="book-container"><div class="book"><div class="page"></div></div><div class="quote-box">"{random.choice(CYTATY_HRABIEGO)}"</div></div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            current_ean = row[ean_col]
            status.text(f"Przetwarzam ({i+1}/{len(df_in)}): {current_ean}")
            
            vars_to_check = generate_variants(current_ean)
            data = get_book_info(vars_to_check)
            
            # Budowa wiersza - teraz czysty słownik dla każdego EAN
            res_row = {"EAN z pliku": current_ean}
            cols = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            
            for c in cols:
                res_row[c] = data.get(c, "Nie znaleziono") if data else "Nie znaleziono"
            
            results.append(res_row)
            bar.progress((i + 1) / len(df_in))
            time.sleep(0.5)

        anim.empty()
        status.success("✅ Gotowe! Wyniki są unikalne dla każdego wiersza.")
        df_res = pd.DataFrame(results)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        st.download_button("📥 Pobierz poprawny Excel", output.getvalue(), "wyniki_poprawne.xlsx")
        st.dataframe(df_res)
