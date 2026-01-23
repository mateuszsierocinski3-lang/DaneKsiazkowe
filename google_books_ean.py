import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="ISBN Multi-Tool", page_icon="📖")

CYTATY_HRABIEGO = [
    "Czekać i mieć nadzieję.",
    "Wszystkie nieszczęścia ludzi płyną z nadziei.",
    "Trzeba zaznać smaku śmierci, by wiedzieć, jak dobrze jest żyć."
]

def clean_ean(ean):
    s = re.sub(r'\D', '', str(ean))
    return s if len(s) >= 10 else ""

def get_data_all_sources(ean):
    """Przeszukuje źródła jedno po drugim, aż znajdzie dane."""
    # Symulacja różnych przeglądarek, by uniknąć blokady IP
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36...',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...'
    ]
    headers = {'User-Agent': random.choice(user_agents)}
    
    data = {k: "Nie znaleziono" for k in ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]}

    # --- 1. GOOGLE BOOKS (Próba bez klucza) ---
    try:
        # Próba ogólna (często skuteczniejsza niż isbn:)
        g_url = f"https://www.googleapis.com/books/v1/volumes?q={ean}"
        res = requests.get(g_url, headers=headers, timeout=5)
        if res.status_code == 200:
            items = res.json().get('items', [])
            if items:
                v = items[0]['volumeInfo']
                ids = v.get('industryIdentifiers', [])
                data.update({
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
                })
                if data["Tytuł"]: return data
    except: pass

    # --- 2. OPEN LIBRARY (Bardzo liberalne API) ---
    try:
        ol_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{ean}&format=json&jscmd=data"
        res = requests.get(ol_url, timeout=5)
        if res.status_code == 200:
            ol_data = res.json().get(f"ISBN:{ean}")
            if ol_data:
                data.update({
                    "Tytuł": ol_data.get('title', ""),
                    "Autor": ", ".join([a['name'] for a in ol_data.get('authors', [])]),
                    "Wydawca": ", ".join([p['name'] for p in ol_data.get('publishers', [])]),
                    "Opublikowane": ol_data.get('publish_date', ""),
                    "Link do okładki": ol_data.get('cover', {}).get('large', ""),
                    "Źródło": "Open Library"
                })
                if data["Tytuł"]: return data
    except: pass

    # --- 3. BIBLIOTEKA NARODOWA (Ostatnia deska ratunku) ---
    try:
        bn_url = f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={ean}"
        res = requests.get(bn_url, timeout=5)
        if res.status_code == 200:
            bibs = res.json().get('bibs', [])
            if bibs:
                data.update({
                    "Tytuł": bibs[0].get('title', ""),
                    "Autor": bibs[0].get('author', ""),
                    "Wydawca": bibs[0].get('publisher', ""),
                    "Opublikowane": bibs[0].get('publicationYear', ""),
                    "Źródło": "BN"
                })
                return data
    except: pass

    return data

# --- UI (Skrócone) ---
st.title("📚 Book Scraper (No-Card Edition)")
file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if file:
    df = pd.read_excel(file)
    col = st.selectbox("Kolumna z EAN:", df.columns)
    
    if st.button("🚀 Start"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            ean = clean_ean(row[col])
            status.text(f"Sprawdzam {ean}...")
            
            # Pobieranie danych
            book_info = get_data_all_sources(ean)
            book_info["EAN z pliku"] = ean
            results.append(book_info)
            
            bar.progress((i+1)/len(df))
            # Losowe opóźnienie, by Google nas nie wyrzuciło
            time.sleep(random.uniform(0.5, 1.2))

        status.success("Gotowe!")
        df_final = pd.DataFrame(results)
        
        # Pobieranie
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, index=False)
        st.download_button("📥 Pobierz Excel", buf.getvalue(), "wynik.xlsx")
        st.dataframe(df_final)
