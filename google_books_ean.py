import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="ISBN Master Pro", page_icon="📚")

# --- CYTATY Z PODPISEM ---
CYTATY_HRABIEGO = [
    "„Czekać i mieć nadzieję.” — Hrabia Monte Christo",
    "„Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!” — Hrabia Monte Christo",
    "„Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają.” — Hrabia Monte Christo",
    "„Trzeba zaznać smaku śmierci, by wiedzieć, jak dobrze jest żyć.” — Hrabia Monte Christo",
    "„Litość jest uczuciem, które najbardziej upodabnia człowieka do Boga.” — Hrabia Monte Christo",
    "„Wszystkie nieszczęścia ludzi płyną z nadziei.” — Hrabia Monte Christo"
]

# --- STYLE CSS (Animacja i Cytat) ---
st.markdown("""
<style>
    .book-container { display: flex; flex-direction: column; align-items: center; padding: 20px; }
    .book { width: 60px; height: 45px; position: relative; perspective: 150px; margin-bottom: 20px; }
    .page { width: 30px; height: 45px; background: white; border: 2px solid #333; position: absolute; right: 0; transform-origin: left; animation: flip 1.2s infinite linear; border-radius: 0 2px 2px 0; }
    .page:nth-child(2) { animation-delay: 0.4s; }
    .page:nth-child(3) { animation-delay: 0.8s; }
    @keyframes flip { 0% { transform: rotateY(0deg); } 100% { transform: rotateY(-180deg); } }
    .book::before { content: ''; position: absolute; width: 30px; height: 45px; background: #eee; border: 2px solid #333; left: 0; border-radius: 2px 0 0 2px; }
    .quote-box { text-align: center; font-family: 'Georgia', serif; font-style: italic; color: #444; background: #f9f9f9; padding: 20px; border-radius: 12px; border-left: 6px solid #1e1e1e; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); max-width: 600px; }
</style>
""", unsafe_allow_html=True)

# --- FUNKCJE POMOCNICZE ---

def get_ean_variants(raw_val):
    """Generuje warianty kodu EAN (z zerem, bez, ISBN-10)."""
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

def fetch_book_data(variants):
    """Przeszukuje bazy danych dla listy wariantów EAN."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'pl-PL,pl;q=0.9'
    }
    
    for ean in variants:
        # 1. GOOGLE BOOKS (Z parametrem hl=pl dla lepszych wyników w PL)
        try:
            for q in [ean, f"isbn:{ean}"]:
                url = f"https://www.googleapis.com/books/v1/volumes?q={q}&hl=pl"
                r = requests.get(url, headers=headers, timeout=5).json()
                if 'items' in r:
                    v = r['items'][0]['volumeInfo']
                    ids = v.get('industryIdentifiers', [])
                    return {
                        "ISBN-13": next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), ean),
                        "ISBN-10": next((i['identifier'] for i in ids if i['type'] == 'ISBN_10'), ""),
                        "Tytuł": v.get('title', "Brak tytułu"),
                        "Autor": ", ".join(v.get('authors', ["Brak danych"])),
                        "Wydawca": v.get('publisher', "Brak danych"),
                        "Opis": v.get('description', "Brak opisu"),
                        "Opublikowane": v.get('publishedDate', ""),
                        "Liczba stron": v.get('pageCount', ""),
                        "Link do okładki": v.get('imageLinks', {}).get('thumbnail', "").replace("http://", "https://"),
                        "Źródło": "Google"
                    }
        except: pass

        # 2. WOLNE LEKTURY
        try:
            url_wl = f"https://wolnelektury.pl/api/books/?isbn={ean}"
            r_wl = requests.get(url_wl, timeout=5).json()
            if r_wl:
                b = r_wl[0]
                return {
                    "Tytuł": b.get('title'),
                    "Autor": b.get('author'),
                    "Wydawca": "Wolne Lektury",
                    "Link do okładki": b.get('simple_thumb'),
                    "Źródło": "Wolne Lektury"
                }
        except: pass

        # 3. BIBLIOTEKA NARODOWA
        try:
            url_bn = f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={ean}"
            r_bn = requests.get(url_bn, timeout=5).json()
            if r_bn.get('bibs'):
                b = r_bn['bibs'][0]
                return {
                    "Tytuł": b.get('title'),
                    "Autor": b.get('author'),
                    "Wydawca": b.get('publisher'),
                    "Opublikowane": b.get('publicationYear'),
                    "Źródło": "BN"
                }
        except: pass

    return None

# --- INTERFEJS UŻYTKOWNIKA ---

st.title("📚 ISBN Multi-Database Scraper")
st.info("Przeszukuje Google Books, Wolne Lektury i Bibliotekę Narodową.")

uploaded_file = st.file_uploader("Wgraj plik Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    col_name = st.selectbox("Wybierz kolumnę z kodami EAN/ISBN:", df_in.columns)
    
    if st.button("🚀 Rozpocznij proces"):
        final_results = []
        progress_bar = st.progress(0)
        status_msg = st.empty()
        anim_placeholder = st.empty()
        
        # Wyświetlenie animacji i cytatu
        cytat = random.choice(CYTATY_HRABIEGO)
        anim_placeholder.markdown(f"""
            <div class="book-container">
                <div class="book"><div class="page"></div><div class="page"></div><div class="page"></div></div>
                <div class="quote-box">{cytat}</div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            raw_ean = row[col_name]
            status_msg.text(f"Pobieranie danych dla: {raw_ean}...")
            
            # 1. Przygotuj warianty
            variants = get_ean_variants(raw_ean)
            
            # 2. Pobierz dane (zawsze wywołujemy funkcję od nowa)
            found_data = fetch_book_data(variants)
            
            # 3. Zbuduj rekord (WAŻNE: słownik 'entry' jest tworzony wewnątrz pętli)
            entry = {"EAN z pliku": raw_ean}
            columns_schema = [
                "ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", 
                "Wydawca", "Opis", "Opublikowane", "Liczba stron", 
                "Link do okładki", "Źródło"
            ]
            
            for col in columns_schema:
                if found_data and col in found_data:
                    entry[col] = found_data[col]
                else:
                    entry[col] = "Nie znaleziono"
            
            final_results.append(entry)
            
            # Aktualizacja postępu
            progress_bar.progress((i + 1) / len(df_in))
            time.sleep(0.4) # Ochrona przed banem IP

        # Czyszczenie po zakończeniu
        anim_placeholder.empty()
        status_msg.success("✅ Przetwarzanie zakończone!")
        
        # Przygotowanie pliku do pobrania
        df_res = pd.DataFrame(final_results)
        output_buffer = io.BytesIO()
        with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Pobierz wynikowy plik Excel",
            data=output_buffer.getvalue(),
            file_name="wyniki_ksiazek.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.dataframe(df_res)
