import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="ISBN Ultimate Multi-Scanner", page_icon="📚")

# --- LISTA CYTATÓW Z PODPISEM ---
CYTATY_HRABIEGO = [
    "„Czekać i mieć nadzieję.” — Hrabia Monte Christo",
    "„Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!” — Aleksander Dumas, Hrabia Monte Christo",
    "„Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają.” — Hrabia Monte Christo",
    "„Trzeba zaznać smaku śmierci, by wiedzieć, jak dobrze jest żyć.” — Hrabia Monte Christo",
    "„Litość jest uczuciem, które najbardziej upodabnia człowieka do Boga.” — Hrabia Monte Christo",
    "„Wszystkie nieszczęścia ludzi płyną z nadziei.” — Hrabia Monte Christo",
    "„Nie ma ani szczęścia, ani nieszczęścia na tym świecie, jest tylko porównanie jednego stanu z drugim.” — Hrabia Monte Christo"
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
    .quote-box { text-align: center; font-family: 'Georgia', serif; font-style: italic; color: #444; background: #f9f9f9; padding: 20px; border-radius: 12px; border-left: 6px solid #1e1e1e; box-shadow: 2px 2px 10px rgba(0,0,0,0.1); max-width: 600px; }
</style>
""", unsafe_allow_html=True)

# --- LOGIKA GENEROWANIA WARIANTÓW ---
def get_clean_variants(raw_val):
    s = str(raw_val).strip()
    if 'E' in s.upper() or '.' in s:
        try: s = "{:.0f}".format(float(raw_val))
        except: pass
    clean = re.sub(r'\D', '', s)
    if not clean: return []
    
    variants = [clean]
    if clean.startswith('0'): variants.append(clean.lstrip('0'))
    if len(clean) == 12: variants.append("0" + clean)
    if len(clean) >= 10: variants.append(clean[-10:])
    return list(dict.fromkeys(variants))

# --- SILNIK POBIERANIA (Z RESTREKCYJNYM CZYSZCZENIEM) ---
def fetch_data(ean_list):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
    
    for ean in ean_list:
        # 1. GOOGLE BOOKS
        try:
            for q in [ean, f"isbn:{ean}"]:
                url = f"https://www.googleapis.com/books/v1/volumes?q={q}"
                r = requests.get(url, headers=headers, timeout=5).json()
                if 'items' in r:
                    v = r['items'][0]['volumeInfo']
                    ids = v.get('industryIdentifiers', [])
                    return {
                        "ISBN-13": next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), ean),
                        "ISBN-10": next((i['identifier'] for i in ids if i['type'] == 'ISBN_10'), ""),
                        "Tytuł": v.get('title', "Brak tytułu"),
                        "Autor": ", ".join(v.get('authors', ["Brak autora"])),
                        "Wydawca": v.get('publisher', "Brak wydawcy"),
                        "Opis": v.get('description', "Brak opisu"),
                        "Opublikowane": v.get('publishedDate', "Brak daty"),
                        "Liczba stron": v.get('pageCount', ""),
                        "Link do okładki": v.get('imageLinks', {}).get('thumbnail', "").replace("http://", "https://"),
                        "Źródło": "Google"
                    }
        except: pass

        # 2. WOLNE LEKTURY
        try:
            r = requests.get(f"https://wolnelektury.pl/api/books/?isbn={ean}", timeout=5).json()
            if r:
                return {"Tytuł": r[0].get('title'), "Autor": r[0].get('author'), "Wydawca": "Wolne Lektury", "Link do okładki": r[0].get('simple_thumb'), "Źródło": "Wolne Lektury"}
        except: pass

        # 3. BIBLIOTEKA NARODOWA (BN)
        try:
            r = requests.get(f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={ean}", timeout=5).json()
            if r.get('bibs'):
                b = r['bibs'][0]
                return {"Tytuł": b.get('title'), "Autor": b.get('author'), "Wydawca": b.get('publisher'), "Opublikowane": b.get('publicationYear'), "Źródło": "BN"}
        except: pass

        # 4. OPEN LIBRARY
        try:
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{ean}&format=json&jscmd=data"
            r = requests.get(url, timeout=5).json()
            if f"ISBN:{ean}" in r:
                ol = r[f"ISBN:{ean}"]
                return {"Tytuł": ol.get('title'), "Autor": ", ".join([a['name'] for a in ol.get('authors', [])]), "Wydawca": ", ".join([p['name'] for p in ol.get('publishers', [])]), "Źródło": "Open Library"}
        except: pass

    return None

# --- UI ---
st.title("📚 ISBN Multi-Variant Scraper")
uploaded_file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    col_name = st.selectbox("Wybierz kolumnę z EAN:", df_in.columns)
    
    if st.button("🚀 Rozpocznij głębokie skanowanie"):
        final_data = []
        prog_bar = st.progress(0)
        status_text = st.empty()
        anim_placeholder = st.empty()
        
        # Animacja i losowy cytat z podpisem
        wybrany_cytat = random.choice(CYTATY_HRABIEGO)
        anim_placeholder.markdown(f"""
            <div class="book-container">
                <div class="book"><div class="page"></div><div class="page"></div><div class="page"></div></div>
                <div class="quote-box">{wybrany_cytat}</div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            raw_ean = row[col_name]
            status_text.text(f"Szukam wariantów dla: {raw_ean}...")
            
            # 1. Generuj warianty (z zerem, bez zera, ISBN-10)
            variants = get_clean_variants(raw_ean)
            
            # 2. Pobierz dane (zwraca None, jeśli we wszystkich bazach brak)
            book_info = fetch_data(variants)
            
            # 3. Buduj wynik (WAŻNE: czysty słownik na każdy wiersz)
            record = {"EAN z pliku": raw_ean}
            headers_list = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            
            for h in headers_list:
                if book_info and h in book_info:
                    record[h] = book_info[h]
                else:
                    record[h] = "Nie znaleziono"
            
            final_data.append(record)
            prog_bar.progress((i + 1) / len(df_in))
            time.sleep(0.4)

        anim_placeholder.empty()
        status_text.success("✅ Przetwarzanie zakończone pomyślnie!")
        
        df_res = pd.DataFrame(final_data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.download_button("📥 Pobierz wynikowy Excel", buffer.getvalue(), "wyniki_isbn_final.xlsx")
        st.dataframe(df_res)
