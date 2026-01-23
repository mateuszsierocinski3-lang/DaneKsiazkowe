import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="ISBN Master Scraper", page_icon="📚")

# --- LISTA CYTATY Z HRABIEGO MONTE CHRISTO ---
CYTATY_HRABIEGO = [
    "Czekać i mieć nadzieję.",
    "Na tym świecie nie ma ani szczęścia, ani nieszczęścia, jest tylko porównanie jednego stanu z drugim.",
    "Litość jest uczuciem, które najbardziej upodabnia człowieka do Boga.",
    "Często przechodzimy obok szczęścia, nie widząc go, nie patrząc na nie, a jeśli nawet je widzieliśmy, to nie poznaliśmy go.",
    "Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!",
    "Trzeba było nieszczęścia, by wydobyć na jaw głębie mego ducha.",
    "Jestem tym, kim jestem: narzędziem w rękach Boga.",
    "Ten, kto nigdy nie pragnął umrzeć, nie wie, jak słodko jest żyć.",
    "Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają."
]

# --- STYLIZACJA CSS (Animacja i cytaty) ---
st.markdown("""
<style>
    .book-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 20px;
    }
    .book {
        width: 60px;
        height: 45px;
        position: relative;
        perspective: 150px;
        margin-bottom: 20px;
    }
    .page {
        width: 30px;
        height: 45px;
        background-color: #fff;
        border: 2px solid #333;
        border-left: none;
        position: absolute;
        right: 0;
        transform-origin: left;
        animation: flip 1.2s infinite linear;
        border-radius: 0 2px 2px 0;
    }
    .page:nth-child(2) { animation-delay: 0.4s; }
    .page:nth-child(3) { animation-delay: 0.8s; }
    
    @keyframes flip {
        0% { transform: rotateY(0deg); }
        100% { transform: rotateY(-180deg); }
    }
    .book::before {
        content: '';
        position: absolute;
        width: 30px;
        height: 45px;
        background: #eee;
        border: 2px solid #333;
        left: 0;
        border-radius: 2px 0 0 2px;
    }
    .hrabia-quote {
        text-align: center;
        font-family: 'Georgia', serif;
        font-style: italic;
        color: #555;
        background: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #0e1117;
        max-width: 500px;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNKCJE LOGICZNE (Na podstawie google_books_ean.py) ---

def normalize_ean(ean):
    """Naprawia błędy formatowania Excela (np. format naukowy) i tworzy warianty."""
    if pd.isna(ean) or str(ean).strip() == "":
        return []
    
    # Obsługa zapisu naukowego (np. 9.78E+12)
    try:
        if 'E' in str(ean).upper() or '.' in str(ean):
            ean_str = "{:.0f}".format(float(ean))
        else:
            ean_str = str(ean).strip()
    except:
        ean_str = str(ean).strip()

    ean_clean = re.sub(r'\D', '', ean_str)
    
    variants = set()
    if ean_clean:
        variants.add(ean_clean)               # Oryginał (cyfry)
        variants.add(ean_clean.lstrip('0'))    # Bez zer na początku
        if len(ean_clean) < 13:
            variants.add(ean_clean.zfill(13)) # Uzupełnione zerami do 13
        if len(ean_clean) >= 10:
            variants.add(ean_clean[-10:])     # Wariant 10-cyfrowy
            
    return list(filter(None, variants))

def get_google_data(ean_variants):
    """Pobiera dane z Google Books sprawdzając warianty EAN."""
    api_url = "https://www.googleapis.com/books/v1/volumes"
    for identifier in ean_variants:
        try:
            res = requests.get(api_url, params={'q': f'isbn:{identifier}'}, timeout=10)
            if res.status_code == 200:
                items = res.json().get('items', [])
                if items:
                    item = items[0]
                    info = item.get('volumeInfo', {})
                    authors = info.get('authors', [])
                    # Uproszczone czyszczenie autorów
                    forbidden = ["wydawnictwo", "uniwersytet", "press", "sp. z o.o.", "publishing"]
                    cleaned_authors = [a for a in authors if not any(f in a.lower() for f in forbidden)]
                    
                    img = info.get('imageLinks', {})
                    cover = img.get('extraLarge') or img.get('large') or img.get('thumbnail', "")
                    
                    return {
                        "Tytuł": info.get('title', "Brak danych"),
                        "Autor": ", ".join(cleaned_authors) if cleaned_authors else "Brak danych",
                        "Wydawca": info.get('publisher', "Brak danych"),
                        "Opis": info.get('description', "Brak opisu"),
                        "Link do okładki": cover.replace("http://", "https://") if cover else "",
                        "Źródło": "Google"
                    }
        except: continue
    return None

def get_bn_publisher(ean_variants):
    """Pobiera wydawcę z Biblioteki Narodowej."""
    api_url = "https://data.bn.org.pl/api/institutions/bibs.json"
    for identifier in ean_variants:
        try:
            res = requests.get(api_url, params={'isbnIssn': identifier}, timeout=10)
            if res.status_code == 200:
                bibs = res.json().get('bibs', [])
                if bibs: return bibs[0].get('publisher', "").strip()
        except: continue
    return None

# --- UI APLIKACJI ---

st.title("📚 Procesor Bazy Książek")
st.write("Wgraj plik Excel, aby automatycznie uzupełnić brakujące dane.")

uploaded_file = st.file_uploader("Dodaj plik Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    df_input = pd.read_excel(uploaded_file)
    kolumna_ean = st.selectbox("Wybierz kolumnę z EAN/ISBN:", df_input.columns)
    
    if st.button("🚀 Rozpocznij mielenie danych"):
        results = []
        progress_bar = st.progress(0)
        
        # Animacja i losowy cytat
        placeholder = st.empty()
        wylosowany_cytat = random.choice(CYTATY_HRABIEGO)
        
        placeholder.markdown(f"""
            <div class="book-container">
                <div class="book">
                    <div class="page"></div><div class="page"></div><div class="page"></div>
                </div>
                <div class="hrabia-quote">
                    "{wylosowany_cytat}"<br>
                    <small>— Hrabia Monte Christo</small>
                </div>
            </div>
        """, unsafe_allow_html=True)

        rows_count = len(df_input)
        for idx, row in df_input.iterrows():
            ean_raw = row[kolumna_ean]
            variants = normalize_ean(ean_raw)
            
            data = None
            if variants:
                data = get_google_data(variants)
                
                # Jeśli brak wydawcy, sprawdź BN
                if not data or data.get('Wydawca') == "Brak danych":
                    bn_pub = get_bn_publisher(variants)
                    if bn_pub:
                        if not data: data = {"Wydawca": bn_pub, "Źródło": "BN"}
                        else: data["Wydawca"] = bn_pub

            # Zbieranie wyników
            res = {"EAN z pliku": ean_raw}
            fields = ["Tytuł", "Autor", "Wydawca", "Opis", "Link do okładki", "Źródło"]
            for f in fields:
                res[f] = data.get(f, "Nie znaleziono") if data else "Nie znaleziono"
            
            results.append(res)
            progress_bar.progress((idx + 1) / rows_count)
            time.sleep(0.05) # Szybkie przetwarzanie

        placeholder.empty()
        st.success("✅ Przetwarzanie zakończone!")
        
        # Przygotowanie pliku do pobrania
        df_final = pd.DataFrame(results)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Pobierz wynikowy plik Excel",
            data=output.getvalue(),
            file_name="wyniki_ksiazki.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.dataframe(df_final.head(10))
