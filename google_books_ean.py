import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA I CYTATY ---
st.set_page_config(page_title="ISBN Master Ultimate", page_icon="📚")

CYTATY_HRABIEGO = [
    "Czekać i mieć nadzieję.",
    "Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!",
    "Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają.",
    "Trzeba zaznać smaku śmierci, by wiedzieć, jak dobrze jest żyć.",
    "Wszystkie nieszczęścia ludzi płyną z nadziei."
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

# --- MECHANIZM AGRESYWNEGO WYSZUKIWANIA ---

def normalize_ean(ean):
    """Czyści EAN z wszelkich błędów Excela."""
    if pd.isna(ean): return ""
    s = str(ean).strip()
    if 'E' in s.upper() or '.' in s:
        try: s = "{:.0f}".format(float(ean))
        except: pass
    return re.sub(r'\D', '', s)

def fetch_book_data(ean):
    """Próbuje dobić do danych Google używając różnych metod zapytania."""
    if not ean: return None
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/110.0.0.0 Safari/537.36'}
    
    # Metody wyszukiwania w kolejności od najbardziej precyzyjnej
    search_methods = [
        f"https://www.googleapis.com/books/v1/volumes?q=isbn:{ean}", # Próba A
        f"https://www.googleapis.com/books/v1/volumes?q={ean}",      # Próba B (ogólna)
    ]
    
    for url in search_methods:
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if 'items' in data:
                    vol = data['items'][0]['volumeInfo']
                    ids = vol.get('industryIdentifiers', [])
                    img = vol.get('imageLinks', {})
                    
                    return {
                        "ISBN-13": next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), ean),
                        "ISBN-10": next((i['identifier'] for i in ids if i['type'] == 'ISBN_10'), "Brak"),
                        "Tytuł": vol.get('title', "Brak danych"),
                        "Autor": ", ".join(vol.get('authors', ["Brak danych"])),
                        "Współtwórca": "",
                        "Wydawca": vol.get('publisher', "Brak danych"),
                        "Opis": vol.get('description', "Brak opisu"),
                        "Opublikowane": vol.get('publishedDate', "Brak"),
                        "Liczba stron": vol.get('pageCount', "Brak"),
                        "Link do okładki": (img.get('thumbnail') or "").replace("http://", "https://"),
                        "Źródło": "Google"
                    }
            time.sleep(0.2) # Krótka przerwa między próbami dla tego samego ISBN
        except:
            continue
    
    # Fallback do Biblioteki Narodowej jeśli Google nic nie dało
    try:
        bn_url = f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={ean}"
        bn_res = requests.get(bn_url, timeout=10)
        if bn_res.status_code == 200:
            bibs = bn_res.json().get('bibs', [])
            if bibs:
                return {
                    "ISBN-13": ean, "ISBN-10": "Brak", "Tytuł": bibs[0].get('title', "Brak danych"),
                    "Autor": bibs[0].get('author', "Brak danych"), "Współtwórca": "",
                    "Wydawca": bibs[0].get('publisher', "Brak danych"), "Opis": "Brak (BN)",
                    "Opublikowane": bibs[0].get('publicationYear', "Brak"), "Liczba stron": "Brak",
                    "Link do okładki": "", "Źródło": "BN"
                }
    except: pass

    return None

# --- APLIKACJA ---

st.title("📚 ISBN Multibaza - Weryfikator")
uploaded_file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    ean_col = st.selectbox("Wybierz kolumnę EAN:", df_in.columns)
    
    if st.button("🚀 Rozpocznij mielenie"):
        results = []
        progress = st.progress(0)
        status = st.empty()
        anim_placeholder = st.empty()
        
        # Animacja i cytat
        anim_placeholder.markdown(f"""
            <div class="book-container">
                <div class="book"><div class="page"></div><div class="page"></div><div class="page"></div></div>
                <div class="quote-box">"{random.choice(CYTATY_HRABIEGO)}"<br><small>— Hrabia Monte Christo</small></div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            raw_ean = normalize_ean(row[ean_col])
            status.text(f"Próba dobicia do: {raw_ean} ({i+1}/{len(df_in)})")
            
            data = fetch_book_data(raw_ean)
            
            # Budowa wiersza (Twoja struktura 1:1)
            entry = {"EAN z pliku": raw_ean}
            cols = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            
            for c in cols:
                entry[c] = data.get(c, "Nie znaleziono") if data else "Nie znaleziono"
            
            results.append(entry)
            progress.progress((i + 1) / len(df_in))
            
            # Dynamiczne opóźnienie (anty-bot)
            time.sleep(random.uniform(0.1, 0.4))

        anim_placeholder.empty()
        status.success("✅ Dane zostały przemielone!")
        
        df_res = pd.DataFrame(results)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.download_button("📥 Pobierz wynikowy Excel", buf.getvalue(), "wyniki_google_bn.xlsx")
        st.dataframe(df_res)
