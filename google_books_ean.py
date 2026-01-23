import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="ISBN Master Fix", page_icon="📚")

# --- CYTATY Z PODPISEM ---
CYTATY_HRABIEGO = [
    "„Czekać i mieć nadzieję.” — Hrabia Monte Christo",
    "„Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!” — Hrabia Monte Christo",
    "„Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają.” — Hrabia Monte Christo",
    "„Trzeba zaznać smaku śmierci, by wiedzieć, jak dobrze jest żyć.” — Hrabia Monte Christo",
    "„Litość jest uczuciem, które najbardziej upodabnia człowieka do Boga.” — Hrabia Monte Christo"
]

# --- STYLE CSS ---
st.markdown("""
<style>
    .book-container { display: flex; flex-direction: column; align-items: center; padding: 20px; }
    .book { width: 60px; height: 45px; position: relative; perspective: 150px; margin-bottom: 20px; }
    .page { width: 30px; height: 45px; background: white; border: 2px solid #333; position: absolute; right: 0; transform-origin: left; animation: flip 1.2s infinite linear; border-radius: 0 2px 2px 0; }
    @keyframes flip { 0% { transform: rotateY(0deg); } 100% { transform: rotateY(-180deg); } }
    .book::before { content: ''; position: absolute; width: 30px; height: 45px; background: #eee; border: 2px solid #333; left: 0; border-radius: 2px 0 0 2px; }
    .quote-box { text-align: center; font-family: 'Georgia', serif; font-style: italic; color: #444; background: #f9f9f9; padding: 20px; border-radius: 12px; border-left: 6px solid #1e1e1e; }
</style>
""", unsafe_allow_html=True)

def get_variants(ean_raw):
    s = re.sub(r'\D', '', str(ean_raw))
    if not s: return []
    v = [s]
    if s.startswith('0'): v.append(s[1:])
    if len(s) == 12: v.append('0' + s)
    if len(s) >= 10: v.append(s[-10:])
    return list(dict.fromkeys(v))

def fetch_book_logic(ean_list):
    """Izolowana funkcja pobierania - nie współdzieli zmiennych między wywołaniami."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    for e in ean_list:
        # 1. GOOGLE
        try:
            r = requests.get(f"https://www.googleapis.com/books/v1/volumes?q={e}", timeout=5).json()
            if 'items' in r:
                v = r['items'][0]['volumeInfo']
                ids = v.get('industryIdentifiers', [])
                return {
                    "ISBN-13": next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), e),
                    "Tytuł": v.get('title', "Brak"), "Autor": ", ".join(v.get('authors', ["Brak"])),
                    "Wydawca": v.get('publisher', "Brak"), "Opis": v.get('description', "Brak"),
                    "Link do okładki": v.get('imageLinks', {}).get('thumbnail', ""), "Źródło": "Google"
                }
        except: pass

        # 2. WOLNE LEKTURY
        try:
            r = requests.get(f"https://wolnelektury.pl/api/books/?isbn={e}", timeout=5).json()
            if r:
                return {"Tytuł": r[0].get('title'), "Autor": r[0].get('author'), "Wydawca": "Wolne Lektury", "Źródło": "Wolne Lektury"}
        except: pass

        # 3. BN
        try:
            r = requests.get(f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={e}", timeout=5).json()
            if r.get('bibs'):
                b = r['bibs'][0]
                return {"Tytuł": b.get('title'), "Autor": b.get('author'), "Wydawca": b.get('publisher'), "Źródło": "BN"}
        except: pass
    return None

# --- STREAMLIT UI ---
st.title("📚 ISBN Multi-Scanner (Fixed Version)")
file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if file:
    df_in = pd.read_excel(file)
    col = st.selectbox("Wybierz kolumnę EAN:", df_in.columns)
    
    if st.button("🚀 Uruchom naprawiony proces"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        anim = st.empty()
        
        anim.markdown(f'<div class="book-container"><div class="book"><div class="page"></div><div class="page"></div></div><div class="quote-box">{random.choice(CYTATY_HRABIEGO)}</div></div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            ean_val = row[col]
            status.text(f"Analiza: {ean_val}")
            
            # GENERUJ I SPRAWDŹ
            variants = get_variants(ean_val)
            book_data = fetch_book_logic(variants)
            
            # BUDUJ WIERSZ OD ZERA
            res_row = {"EAN z pliku": ean_val}
            keys = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            
            for k in keys:
                if book_data and k in book_data:
                    res_row[k] = book_data[k]
                else:
                    res_row[k] = "Nie znaleziono"
            
            results.append(res_row)
            bar.progress((i + 1) / len(df_in))
            time.sleep(0.3)

        anim.empty()
        status.success("✅ Sukces! Każdy wiersz ma teraz własne dane.")
        df_res = pd.DataFrame(results)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        st.download_button("📥 Pobierz poprawny Excel", output.getvalue(), "naprawione_wyniki.xlsx")
        st.dataframe(df_res)
