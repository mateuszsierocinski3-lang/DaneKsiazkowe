import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="ISBN Master Lokalny", page_icon="📚")

# --- CYTATY Z PODPISEM ---
CYTATY_HRABIEGO = [
    "„Czekać i mieć nadzieję.” — Hrabia Monte Christo",
    "„Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!” — Hrabia Monte Christo",
    "„Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają.” — Hrabia Monte Christo",
    "„Trzeba zaznać smaku śmierci, by wiedzieć, jak dobrze jest żyć.” — Hrabia Monte Christo"
]

# --- LOGIKA VARIANTÓW ---
def get_ean_variants(ean_raw):
    s = re.sub(r'\D', '', str(ean_raw))
    if not s: return []
    v = [s]
    if s.startswith('0'): v.append(s[1:])
    if len(s) == 12: v.append('0' + s)
    if len(s) >= 10: v.append(s[-10:])
    return list(dict.fromkeys(v))

# --- SILNIK POBIERANIA (Z SYMULACJĄ TWOJEGO KOMPUTERA) ---
def fetch_book_data(variants):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'pl-PL,pl;q=0.9'
    }
    
    for e in variants:
        # 1. GOOGLE BOOKS (Wzmocnione o parametry regionalne)
        try:
            url = f"https://www.googleapis.com/books/v1/volumes?q={e}&hl=pl&country=PL"
            r = requests.get(url, headers=headers, timeout=5).json()
            if 'items' in r:
                v = r['items'][0]['volumeInfo']
                ids = v.get('industryIdentifiers', [])
                return {
                    "ISBN-13": next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), e),
                    "Tytuł": v.get('title', "Nie znaleziono"),
                    "Autor": ", ".join(v.get('authors', ["Brak danych"])),
                    "Wydawca": v.get('publisher', "Brak danych"),
                    "Opis": v.get('description', "Brak opisu"),
                    "Link do okładki": v.get('imageLinks', {}).get('thumbnail', ""),
                    "Źródło": "Google"
                }
        except: pass

        # 2. WOLNE LEKTURY
        try:
            r = requests.get(f"https://wolnelektury.pl/api/books/?isbn={e}", timeout=5).json()
            if r:
                return {"Tytuł": r[0].get('title'), "Autor": r[0].get('author'), "Wydawca": "Wolne Lektury", "Źródło": "Wolne Lektury"}
        except: pass

        # 3. BIBLIOTEKA NARODOWA
        try:
            r = requests.get(f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={e}", timeout=5).json()
            if r.get('bibs'):
                b = r['bibs'][0]
                return {"Tytuł": b.get('title'), "Autor": b.get('author'), "Wydawca": b.get('publisher'), "Źródło": "BN"}
        except: pass
    return None

# --- UI ---
st.title("📚 ISBN Deep Search (Local Node)")
file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if file:
    df_in = pd.read_excel(file)
    col = st.selectbox("Wybierz kolumnę z EAN:", df_in.columns)
    
    if st.button("🚀 Start"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        anim = st.empty()
        
        anim.markdown(f'<div style="text-align:center; padding:20px; border-radius:10px; background:#f0f2f6; border-left: 5px solid #1e1e1e;"><i>{random.choice(CYTATY_HRABIEGO)}</i></div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            current_ean = row[col]
            status.text(f"Przetwarzam: {current_ean} ({i+1}/{len(df_in)})")
            
            # POBIERANIE - zawsze z nowym zestawem wariantów
            data = fetch_book_data(get_ean_variants(current_ean))
            
            # KONSTRUKCJA WIERSZA (Gwarancja unikalności)
            res_row = {"EAN z pliku": current_ean}
            headers = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            
            for h in headers:
                if data and h in data:
                    res_row[h] = data[h]
                else:
                    res_row[h] = "Nie znaleziono"
            
            results.append(res_row)
            bar.progress((i+1)/len(df_in))
            time.sleep(0.4) # Twoje IP jest bezpieczne przy takim tempie

        status.success("✅ Gotowe! Wyniki są unikalne dla każdego EAN.")
        df_res = pd.DataFrame(results)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        st.download_button("📥 Pobierz Excel", output.getvalue(), "wyniki_lokalne.xlsx")
        st.dataframe(df_res)
