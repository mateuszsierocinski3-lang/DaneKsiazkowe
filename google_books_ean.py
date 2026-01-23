import streamlit as st
import pandas as pd
import requests
import time
import re
import io

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Book Data Scraper", page_icon="📚")

# --- STYLIZACJA CSS (Animacja książki) ---
st.markdown("""
<style>
    .book {
      position: relative;
      width: 60px;
      height: 40px;
      margin: 20px auto;
      border: 2px solid #333;
      border-radius: 2px;
    }
    .book__page {
      position: absolute;
      top: 0;
      right: 0;
      width: 50%;
      height: 100%;
      background: white;
      border-left: 1px solid #333;
      transform-origin: left center;
      animation: flip 1s infinite linear;
    }
    @keyframes flip {
      0% { transform: rotateY(0deg); }
      100% { transform: rotateY(-180deg); }
    }
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNKCJE LOGICZNE (Kopia Twojej logiki) ---

def get_bn_publisher_only(ean):
    ean_clean = re.sub(r'\D', '', str(ean))
    api_url = "https://data.bn.org.pl/api/institutions/bibs.json"
    try:
        response = requests.get(api_url, params={'isbnIssn': ean_clean}, timeout=10)
        if response.status_code == 200:
            bibs = response.json().get('bibs', [])
            if bibs:
                return bibs[0].get('publisher', "").strip()
    except: pass
    return None

def get_open_library_data(ean):
    ean_clean = re.sub(r'\D', '', str(ean))
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{ean_clean}&format=json&jscmd=data"
    try:
        res = requests.get(url, timeout=10).json()
        key = f"ISBN:{ean_clean}"
        if key in res:
            b = res[key]
            return {
                "Tytuł": b.get('title', ""),
                "Autor": ", ".join([a['name'] for a in b.get('authors', [])]),
                "Wydawca": ", ".join([p['name'] for p in b.get('publishers', [])]),
                "Opis": b.get('notes', ""),
                "Okładka": b.get('cover', {}).get('large', ""),
                "Źródło": "Open Library"
            }
    except: pass
    return None

def clean_author_and_publisher(raw_authors, raw_pub):
    forbidden = ["wydawnictwo", "uniwersytet", "university", "press", "sp. z o.o.", "publishing", "wydaw"]
    cleaned_authors = []
    extracted_pub = raw_pub if raw_pub else ""
    if not raw_authors:
        return "Brak danych", extracted_pub
    for item in raw_authors:
        if any(word in item.lower() for word in forbidden):
            if not extracted_pub:
                extracted_pub = item.strip()
        else:
            cleaned_authors.append(item.strip())
    author_final = ", ".join(cleaned_authors) if cleaned_authors else "Brak danych"
    return author_final, extracted_pub

def get_google_data(ean):
    ean_clean = re.sub(r'\D', '', str(ean))
    variants = [ean_clean, ean_clean.lstrip('0')]
    if len(ean_clean) >= 10: variants.append(ean_clean[-10:])
    api_url = "https://www.googleapis.com/books/v1/volumes"
    for identifier in list(dict.fromkeys(variants)):
        try:
            res = requests.get(api_url, params={'q': f'isbn:{identifier}'}, timeout=10)
            if res.status_code == 200:
                items = res.json().get('items', [])
                if items:
                    item = items[0]
                    info = item.get('volumeInfo', {})
                    g_pub = info.get('publisher', '')
                    author, publisher = clean_author_and_publisher(info.get('authors', []), g_pub)
                    ids = info.get('industryIdentifiers', [])
                    i10 = next((i['identifier'] for i in ids if i['type'] == 'ISBN_10'), "Brak")
                    i13 = next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), "Brak")
                    img = info.get('imageLinks', {})
                    cover = img.get('extraLarge') or img.get('large') or img.get('thumbnail', "")
                    return {
                        "ISBN-13": i13,
                        "ISBN-10": i10,
                        "Tytuł": info.get('title', "Brak danych"),
                        "Autor": author,
                        "Współtwórca": ", ".join(info.get('contributors', [])),
                        "Wydawca": publisher,
                        "Opis": info.get('description', "Brak opisu"),
                        "Opublikowane": info.get('publishedDate', "Brak"),
                        "Liczba stron": info.get('pageCount', "Brak"),
                        "Link do okładki": cover.replace("http://", "https://") if cover else "Brak okładki",
                        "Źródło": "Google"
                    }
        except: continue
    return None

# --- INTERFEJS UŻYTKOWNIKA ---

st.title("📚 Pobieranie Danych o Książkach")
st.write("Wgraj plik Excel z kolumną EAN/ISBN, aby automatycznie uzupełnić dane z Google Books, Open Library i BN.")

uploaded_file = st.file_uploader("Wybierz plik Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    df_input = pd.read_excel(uploaded_file)
    st.success(f"Wczytano plik: {uploaded_file.name}")
    
    # Wybór kolumny z EAN
    kolumna_ean = st.selectbox("Wybierz kolumnę zawierającą numery EAN/ISBN:", df_input.columns)
    
    if st.button("🚀 Rozpocznij przetwarzanie"):
        final_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Miejsce na animację książki
        book_anim = st.empty()
        book_anim.markdown('<div class="book"><div class="book__page"></div></div>', unsafe_allow_html=True)

        total_rows = len(df_input)

        for idx, row in df_input.iterrows():
            ean = str(row[kolumna_ean]).strip()
            if ean.upper() in ["EAN", "NAN", ""]: 
                progress_bar.progress((idx + 1) / total_rows)
                continue

            status_text.text(f"Przetwarzanie {idx+1}/{total_rows}: {ean}")
            
            # 1. Google
            data = get_google_data(ean)
            
            # 2. Open Library
            if not data or data.get('Tytuł') == "Brak danych":
                ol_data = get_open_library_data(ean)
                if ol_data:
                    data = {
                        "ISBN-13": ean,
                        "Tytuł": ol_data["Tytuł"],
                        "Autor": ol_data["Autor"],
                        "Wydawca": ol_data["Wydawca"],
                        "Opis": ol_data["Opis"],
                        "Link do okładki": ol_data["Okładka"],
                        "Źródło": "Open Library"
                    }

            # 3. BN
            if data:
                if not data.get('Wydawca') or data.get('Wydawca') == "":
                    bn_pub = get_bn_publisher_only(ean)
                    if bn_pub:
                        data['Wydawca'] = bn_pub
            else:
                bn_pub = get_bn_publisher_only(ean)
                data = {"Wydawca": bn_pub if bn_pub else "Nie znaleziono", "Źródło": "BN"}

            # Mapowanie wyniku
            res = {"EAN z pliku": ean}
            fields = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            for f in fields:
                res[f] = data.get(f, "Nie znaleziono") if data else "Nie znaleziono"
            
            final_results.append(res)
            
            # Aktualizacja paska postępu
            progress_bar.progress((idx + 1) / total_rows)
            time.sleep(0.1) # Lekkie opóźnienie, by nie przeciążyć API

        # Czyszczenie po zakończeniu
        book_anim.empty()
        status_text.success("✅ Przetwarzanie zakończone!")
        
        # Przygotowanie pliku do pobrania
        output_df = pd.DataFrame(final_results)
        
        # Konwersja do Excela w pamięci
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            output_df.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Pobierz wynikowy plik Excel",
            data=output.getvalue(),
            file_name="wyniki_ksiazki.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.write("Podgląd wyników:")
        st.dataframe(output_df.head(10))
