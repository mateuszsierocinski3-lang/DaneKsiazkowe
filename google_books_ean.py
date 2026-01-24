import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Sunnyvale Deep-JSON Scanner", page_icon="🥃")

# --- CYTATY Z CHŁOPAKÓW Z BARAKÓW ---
CYTATY_CHLOPAKI = [
    "„To nie jest żadne rocket appliances.” — Ricky",
    "„Zasady są proste: nie jesz moich pepperoni i nie pijesz mojego soku.” — Ricky",
    "„Czujesz to? To gówniany wiatr wieje.” — Jim Lahey",
    "„Julian, on pije wodę z psem! To jest obrzydliwe!” — Bubbles",
    "„Praca jest dla ludzi, którzy nie wiedzą, jak kraść.” — Ricky",
    "„Mamy przechlapane, Julian. Całkowicie przechlapane.” — Bubbles",
    "„Dobra, Cory, Trevor, fajki już!” — Ricky"
]

# --- STYLE CSS (Styl baraków) ---
st.markdown("""
<style>
    .quote-box { 
        text-align: center; 
        font-family: 'Courier New', monospace; 
        font-weight: bold; 
        color: #1a1a1a;
        background: #fdfd96; 
        padding: 20px; 
        border: 3px solid #333; 
        box-shadow: 8px 8px 0px #000;
        margin: 20px 0;
    }
    .stButton>button {
        background-color: #333;
        color: white;
        border-radius: 0px;
        border: 2px solid #000;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNKCJE LOGICZNE ---

def fetch_deep_ol_data(isbn):
    """
    Pobiera i mapuje dane dokładnie wg Twojej struktury JSON z Postmana.
    Używa jscmd=details, aby dostać się do najgłębszych warstw bazy.
    """
    try:
        # Czyszczenie ISBN (tylko cyfry)
        isbn_clean = re.sub(r'\D', '', str(isbn))
        if not isbn_clean:
            return None
            
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=details"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            res_json = response.json()
            key = f"ISBN:{isbn_clean}"
            
            if key in res_json:
                book_data = res_json[key].get('data', {})
                details = res_json[key].get('details', {})
                
                # Mapowanie pól z Twojego JSONa
                return {
                    "Tytuł": book_data.get('title'),
                    "Podtytuł": book_data.get('subtitle', ""),
                    "Autorzy": ", ".join([a['name'] for a in book_data.get('authors', [])]),
                    "Wydawcy": ", ".join([p['name'] for p in book_data.get('publishers', [])]),
                    "Miejsca wydania": ", ".join([p['name'] for p in book_data.get('publish_places', [])]),
                    "Kraj wydania": details.get('publish_country', ""),
                    "Data publikacji": book_data.get('publish_date'),
                    "Liczba stron": book_data.get('number_of_pages'),
                    "Pagynacja": book_data.get('pagination', ""),
                    "Opis/Notatki": str(book_data.get('notes', "")),
                    "Tematy (Subjects)": ", ".join([s['name'] for s in book_data.get('subjects', [])]),
                    "Miejsca (Subject Places)": ", ".join([p['name'] for p in book_data.get('subject_places', [])]),
                    "Czasy (Subject Times)": ", ".join([t['name'] for t in book_data.get('subject_times', [])]),
                    "Języki": ", ".join([l.get('key', '').split('/')[-1] for l in details.get('languages', [])]),
                    "Klasyfikacja LC": ", ".join(details.get('lc_classifications', [])),
                    "ISBN-10": ", ".join(details.get('isbn_10', [])),
                    "LCCN": ", ".join(details.get('lccn', [])),
                    "OCLC": ", ".join(details.get('oclc_numbers', [])),
                    "Goodreads ID": ", ".join(details.get('identifiers', {}).get('goodreads', [])),
                    "Link do okładki (L)": book_data.get('cover', {}).get('large', ""),
                    "URL Open Library": book_data.get('url', ""),
                    "Źródło": "Open Library Deep JSON"
                }
    except Exception:
        return None
    return None

# --- INTERFEJS UŻYTKOWNIKA ---

st.title("🥃 Sunnyvale Deep-JSON Scraper")
st.markdown("### *„Dobra, Julian, bierzemy ten towar z Open Library i spadamy!”*")

uploaded_file = st.file_uploader("Wgraj plik Excel (ISBN)", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    col_name = st.selectbox("Wybierz kolumnę z ISBN/EAN:", df_in.columns)
    
    if st.button("🚀 Odpal Głębokie Skanowanie"):
        final_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        quote_area = st.empty()
        
        # Wyświetlenie losowego cytatu na czas pracy
        quote_area.markdown(f'<div class="quote-box">{random.choice(CYTATY_CHLOPAKI)}</div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            isbn_to_search = row[col_name]
            status_text.text(f"Przeszukuję baraki... Sprawdzam: {isbn_to_search}")
            
            # POBIERANIE DANYCH (zawsze od zera dla każdego wiersza)
            found_book = fetch_deep_ol_data(isbn_to_search)
            
            # Tworzenie rekordu
            record = {"EAN wejściowy": isbn_to_search}
            
            # Lista wszystkich kolumn (pobrana z Twojego JSONa)
            all_headers = [
                "Tytuł", "Podtytuł", "Autorzy", "Wydawcy", "Miejsca wydania", 
                "Kraj wydania", "Data publikacji", "Liczba stron", "Pagynacja", 
                "Opis/Notatki", "Tematy (Subjects)", "Miejsca (Subject Places)", 
                "Czasy (Subject Times)", "Języki", "Klasyfikacja LC", "ISBN-10", 
                "LCCN", "OCLC", "Goodreads ID", "Link do okładki (L)", "URL Open Library", "Źródło"
            ]
            
            for h in all_headers:
                if found_book and h in found_book:
                    record[h] = found_book[h]
                else:
                    record[h] = "Brak danych"
            
            final_results.append(record)
            
            # Aktualizacja paska postępu
            progress_bar.progress((i + 1) / len(df_in))
            time.sleep(0.2) # Stabilizacja dla serwerów OL

        # Zakończenie pracy
        quote_area.empty()
        status_text.success("✅ Julian, towar jest na pace! Wszystko przemycone do Excela.")
        
        # Konwersja na DataFrame i przygotowanie do pobrania
        df_res = pd.DataFrame(final_results)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Pobierz Pełny Transport Danych (Excel)",
            data=output.getvalue(),
            file_name="sunnyvale_deep_scan_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Podgląd wyników
        st.write("### Podgląd wyników:")
        st.dataframe(df_res)
