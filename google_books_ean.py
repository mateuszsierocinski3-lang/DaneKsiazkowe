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
    "Czekać i mieć nadzieję.",
    "Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!",
    "Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają.",
    "Jestem tym, kim jestem: narzędziem w rękach Boga.",
    "Wszystkie nieszczęścia ludzi płyną z nadziei.",
    "Trzeba zaznać smaku śmierci, by wiedzieć, jak dobrze jest żyć."
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

# --- FUNKCJE POMOCNICZE ---

def clean_ean_to_string(ean):
    """Konwertuje EAN na czysty ciąg cyfr, odporny na formaty Excela."""
    if pd.isna(ean): return ""
    s = str(ean).strip()
    # Jeśli jest kropka lub E (format naukowy), przelicz na int
    if '.' in s or 'E' in s.upper():
        try:
            s = "{:.0f}".format(float(ean))
        except:
            pass
    return re.sub(r'\D', '', s)

def fetch_from_google(ean):
    """Próbuje znaleźć książkę w Google na dwa sposoby."""
    if not ean: return None
    
    # Próbujemy dwóch typów zapytań
    search_queries = [f"isbn:{ean}", f"{ean}"]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    for q in search_queries:
        try:
            url = f"https://www.googleapis.com/books/v1/volumes?q={q}"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if 'items' in data:
                    vol = data['items'][0]['volumeInfo']
                    ids = vol.get('industryIdentifiers', [])
                    i13 = next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), ean)
                    i10 = next((i['identifier'] for i in ids if i['type'] == 'ISBN_10'), "Brak")
                    img = vol.get('imageLinks', {})
                    cover = img.get('extraLarge') or img.get('large') or img.get('thumbnail') or "Brak okładki"
                    
                    return {
                        "ISBN-13": i13,
                        "ISBN-10": i10,
                        "Tytuł": vol.get('title', "Brak danych"),
                        "Autor": ", ".join(vol.get('authors', ["Brak danych"])),
                        "Współtwórca": "", 
                        "Wydawca": vol.get('publisher', "Brak danych"),
                        "Opis": vol.get('description', "Brak opisu"),
                        "Opublikowane": vol.get('publishedDate', "Brak"),
                        "Liczba stron": vol.get('pageCount', "Brak"),
                        "Link do okładki": cover.replace("http://", "https://") if "http" in cover else cover,
                        "Źródło": "Google"
                    }
        except:
            continue
    return None

def fetch_from_bn(ean):
    """Fallback do Biblioteki Narodowej."""
    try:
        url = f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={ean}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            bibs = res.json().get('bibs', [])
            if bibs:
                b = bibs[0]
                return {
                    "ISBN-13": ean, "ISBN-10": "Brak",
                    "Tytuł": b.get('title', "Brak danych"),
                    "Autor": b.get('author', "Brak danych"),
                    "Współtwórca": "", "Wydawca": b.get('publisher', "Brak danych"),
                    "Opis": "Brak opisu (BN)", "Opublikowane": b.get('publicationYear', "Brak"),
                    "Liczba stron": "Brak", "Link do okładki": "Brak okładki", "Źródło": "BN"
                }
    except: pass
    return None

# --- UI STREAMLIT ---

st.title("📚 ISBN Multibaza - Weryfikator")
uploaded_file = st.file_uploader("Wgraj plik z kolumną EAN", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    ean_col = st.selectbox("Wybierz kolumnę z numerami:", df_in.columns)
    
    if st.button("🚀 Rozpocznij sprawdzanie"):
        results = []
        progress = st.progress(0)
        status = st.empty()
        
        # Animacja + Cytat
        anim_placeholder = st.empty()
        anim_placeholder.markdown(f"""
            <div class="book-container">
                <div class="book"><div class="page"></div><div class="page"></div><div class="page"></div></div>
                <div class="quote-box">"{random.choice(CYTATY_HRABIEGO)}"<br><small>— Hrabia Monte Christo</small></div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            ean_raw = clean_ean_to_string(row[ean_col])
            status.text(f"Przetwarzam: {ean_raw}")
            
            # Próba 1: Google
            data = fetch_from_google(ean_raw)
            
            # Próba 2: BN (jeśli Google zawiedzie)
            if not data:
                data = fetch_from_bn(ean_raw)
            
            # Budowanie wiersza zgodnie ze schematem
            entry = {"EAN z pliku": ean_raw}
            cols = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            
            for c in cols:
                entry[c] = data.get(c, "Nie znaleziono") if data else "Nie znaleziono"
            
            results.append(entry)
            progress.progress((i + 1) / len(df_in))
            time.sleep(0.1) # Delikatne opóźnienie dla stabilności API

        anim_placeholder.empty()
        status.success("✅ Przetwarzanie zakończone!")
        
        df_res = pd.DataFrame(results)
        
        # Export do Excela
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.download_button("📥 Pobierz wynikowy Excel", output.getvalue(), "wynik_isbn.xlsx")
        st.dataframe(df_res)
