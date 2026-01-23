import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="ISBN Master Pro", page_icon="📚")

CYTATY_HRABIEGO = [
    "„Czekać i mieć nadzieję.” — Hrabia Monte Christo",
    "„Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!” — Hrabia Monte Christo",
    "„Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają.” — Hrabia Monte Christo",
    "„Trzeba zaznać smaku śmierci, by wiedzieć, jak dobrze jest żyć.” — Hrabia Monte Christo"
]

# --- STYLE CSS (Książka i Cytat) ---
st.markdown("""
<style>
    .book-container { display: flex; flex-direction: column; align-items: center; padding: 20px; }
    .book { width: 60px; height: 45px; position: relative; perspective: 150px; margin-bottom: 20px; }
    .page { width: 30px; height: 45px; background: white; border: 2px solid #333; position: absolute; right: 0; transform-origin: left; animation: flip 1.2s infinite linear; border-radius: 0 2px 2px 0; }
    @keyframes flip { 0% { transform: rotateY(0deg); } 100% { transform: rotateY(-180deg); } }
    .quote-box { text-align: center; font-family: 'Georgia', serif; font-style: italic; color: #444; background: #f9f9f9; padding: 20px; border-radius: 12px; border-left: 6px solid #1e1e1e; max-width: 600px; }
</style>
""", unsafe_allow_html=True)

# --- FUNKCJE LOGICZNE ---

def get_ean_variants(ean_raw):
    s = re.sub(r'\D', '', str(ean_raw))
    if not s: return []
    v = [s]
    if s.startswith('0'): v.append(s[1:])
    if len(s) == 12: v.append('0' + s)
    if len(s) >= 10: v.append(s[-10:])
    return list(dict.fromkeys(v))

def fetch_book_info(variants):
    """
    Kluczowa funkcja: Każde wywołanie zaczyna z pustym słownikiem, 
    co zapobiega powielaniu wyników.
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    
    for e in variants:
        # 1. PRÓBA: WOLNE LEKTURY (API)
        try:
            # Wolne Lektury zwracają listę. Jeśli pusta - idziemy dalej.
            r = requests.get(f"https://wolnelektury.pl/api/books/?isbn={e}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data and len(data) > 0:
                    book = data[0]
                    return {
                        "Tytuł": book.get('title'),
                        "Autor": book.get('author'),
                        "Wydawca": "Wolne Lektury",
                        "Link do okładki": book.get('simple_thumb'),
                        "Źródło": "Wolne Lektury"
                    }
        except: pass

        # 2. PRÓBA: GOOGLE BOOKS
        try:
            url = f"https://www.googleapis.com/books/v1/volumes?q={e}&hl=pl"
            r = requests.get(url, headers=headers, timeout=5).json()
            if 'items' in r:
                v = r['items'][0]['volumeInfo']
                return {
                    "Tytuł": v.get('title'),
                    "Autor": ", ".join(v.get('authors', [])),
                    "Wydawca": v.get('publisher'),
                    "Opis": v.get('description', ""),
                    "Źródło": "Google"
                }
        except: pass

        # 3. PRÓBA: BIBLIOTEKA NARODOWA
        try:
            r = requests.get(f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={e}", timeout=5).json()
            if r.get('bibs'):
                b = r['bibs'][0]
                return {"Tytuł": b.get('title'), "Autor": b.get('author'), "Wydawca": b.get('publisher'), "Źródło": "BN"}
        except: pass

    return None # Jeśli żaden wariant w żadnej bazie nie zadziałał

# --- APLIKACJA ---

st.title("📚 ISBN Multi-Scanner (Unique Mode)")
uploaded_file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    col = st.selectbox("Kolumna z EAN:", df_in.columns)
    
    if st.button("🚀 Start"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        anim = st.empty()
        
        # Losowy cytat Hrabiego
        anim.markdown(f'<div class="book-container"><div class="book"><div class="page"></div></div><div class="quote-box">{random.choice(CYTATY_HRABIEGO)}</div></div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            current_ean = row[col]
            status.text(f"Sprawdzam: {current_ean}...")
            
            # Resetujemy 'found_data' dla każdego wiersza!
            variants = get_ean_variants(current_ean)
            found_data = fetch_book_info(variants)
            
            # Budujemy rekord - jeśli found_data jest None, wpisze "Nie znaleziono"
            res_row = {"EAN z pliku": current_ean}
            headers = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            
            for h in headers:
                if found_data and h in found_data:
                    res_row[h] = found_data[h]
                else:
                    res_row[h] = "Nie znaleziono"
            
            results.append(res_row)
            bar.progress((i + 1) / len(df_in))
            time.sleep(0.3)

        anim.empty()
        status.success("✅ Gotowe! Sprawdź czy wyniki są unikalne.")
        
        df_res = pd.DataFrame(results)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.download_button("📥 Pobierz Excel", buf.getvalue(), "wyniki_unikalne.xlsx")
        st.dataframe(df_res)
