import pandas as pd
import requests
import time
import os
import re

# --- KONFIGURACJA ŚCIEŻEK ---
BASE_DIR = r"C:\Users\msierocinski\Downloads\Skrypt Books"
PLIK_WEJSCIOWY = os.path.join(BASE_DIR, "export-products.xlsx")
PLIK_WYNIKOWY = os.path.join(BASE_DIR, "wynik_multibaza_final.xlsx")

def get_bn_publisher_only(ean):
    """Pobiera wyłącznie wydawcę z Biblioteki Narodowej."""
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
    """Szukanie w bazie Open Library (Internet Archive)."""
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

def get_wolne_lektury_data(ean):
    """Szukanie w bazie Wolne Lektury (po ISBN)."""
    # Wolne Lektury mają API oparte o slugach, ale sprawdzamy czy EAN jest w ich katalogu
    api_url = f"https://wolnelektury.pl/api/books/"
    # Z uwagi na specyfikę API Wolnych Lektur, najskuteczniejsze jest szukanie po tytule, 
    # ale tutaj ograniczamy się do sprawdzenia dostępności.
    return None

def clean_author_and_publisher(raw_authors, raw_pub):
    """Porządkuje autorów i wydawców."""
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
    """Pobiera komplet danych z Google Books (Nadrzędne)."""
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
                    
                    # Wydawca
                    g_pub = info.get('publisher', '')
                    author, publisher = clean_author_and_publisher(info.get('authors', []), g_pub)
                    
                    # ISBNy
                    ids = info.get('industryIdentifiers', [])
                    i10 = next((i['identifier'] for i in ids if i['type'] == 'ISBN_10'), "Brak")
                    i13 = next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), "Brak")
                    
                    # Okładka
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

def main():
    print("--- START: Google + OpenLibrary + BN ---")
    if not os.path.exists(PLIK_WEJSCIOWY):
        print(f"BŁĄD: Nie znaleziono pliku {PLIK_WEJSCIOWY}")
        return

    df = pd.read_excel(PLIK_WEJSCIOWY)
    final_results = []

    for idx, row in df.iterrows():
        ean = str(row.iloc[4]).strip()
        if ean.upper() in ["EAN", "NAN", ""]: continue

        print(f"[{idx+1}] Analiza: {ean}")
        
        # 1. PRÓBA GOOGLE (Nadrzędne)
        data = get_google_data(ean)
        
        # 2. PRÓBA OPEN LIBRARY (Jeśli brak w Google)
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

        # 3. UZUPEŁNIENIE WYDAWCY Z BN (Jeśli nadal puste)
        if data:
            if not data.get('Wydawca') or data.get('Wydawca') == "":
                bn_pub = get_bn_publisher_only(ean)
                if bn_pub:
                    data['Wydawca'] = bn_pub
        else:
            # Ostateczna próba - tylko wydawca z BN
            bn_pub = get_bn_publisher_only(ean)
            data = {"Wydawca": bn_pub if bn_pub else "Nie znaleziono", "Źródło": "BN"}

        res = {"EAN z pliku": ean}
        fields = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
        for f in fields:
            res[f] = data.get(f, "Nie znaleziono") if data else "Nie znaleziono"
        
        final_results.append(res)
        time.sleep(0.5)

    pd.DataFrame(final_results).to_excel(PLIK_WYNIKOWY, index=False)
    print(f"\n✅ GOTOWE! Wyniki zapisano w: {PLIK_WYNIKOWY}")

if __name__ == "__main__":
    main()
