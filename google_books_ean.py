import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="Sunnyvale Super Deep Scan", page_icon="🥃")

CYTATY_CHLOPAKI = [
    "„To nie jest żadne rocket appliances.” — Ricky",
    "„Zasady są proste: nie jesz moich pepperoni i nie pijesz mojego soku.” — Ricky",
    "„Czujesz to? To gówniany wiatr wieje.” — Jim Lahey",
    "„Julian, on pije wodę z psem! To jest obrzydliwe!” — Bubbles"
]

st.markdown("""
<style>
    .quote-box { text-align: center; font-family: 'Courier New', monospace; font-weight: bold; background: #fdfd96; padding: 15px; border: 3px solid #333; box-shadow: 6px 6px 0px #000; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- POPRAWIONA LOGIKA POBIERANIA (BEZ PODTYTUŁU + FIX OKŁADKI) ---

def fetch_book_data_v3(isbn):
    isbn_clean = re.sub(r'\D', '', str(isbn))
    if not isbn_clean: return None
    
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=details"
    
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            res = r.json()
            key = f"ISBN:{isbn_clean}"
            if key in res:
                d_main = res[key].get('data', {})
                d_details = res[key].get('details', {})
                
                # 1. Tytuł (zawsze bierzemy główny)
                title = d_main.get('title') or d_details.get('title')
                
                # 2. Autorzy
                authors_list = d_main.get('authors') or d_details.get('authors')
                authors = "Nieznany"
                if authors_list:
                    authors = ", ".join([a.get('name', 'Nieznany') for a in authors_list])

                # 3. Logika okładki (sprawdzamy 3 miejsca)
                cover_url = "Brak okładki"
                # Miejsce A: Główny obiekt thumbnail_url
                if res[key].get('thumbnail_url'):
                    cover_url = res[key].get('thumbnail_url').replace("-S.jpg", "-L.jpg")
                # Miejsce B: Obiekt 'cover' w data
                elif d_main.get('cover', {}).get('large'):
                    cover_url = d_main.get('cover', {}).get('large')
                # Miejsce C: Lista 'covers' w details (ID obrazka)
                elif d_details.get('covers'):
                    cover_id = d_details.get('covers')[0]
                    if cover_id and cover_id != -1:
                        cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

                # Funkcja pomocnicza do list
                def get_clean_list(field_name):
                    data = d_main.get(field_name) or d_details.get(field_name) or []
                    if not data: return ""
                    if isinstance(data[0], dict):
                        return ", ".join([x.get('name', str(x)) for x in data])
                    return ", ".join([str(x) for x in data])

                return {
                    "Tytuł": title,
                    "Autorzy": authors,
                    "Wydawcy": get_clean_list('publishers'),
                    "Miejsca wydania": get_clean_list('publish_places') or get_clean_list('publish_place'),
                    "Kraj wydania": d_details.get('publish_country', ""),
                    "Data publikacji": d_main.get('publish_date') or d_details.get('publish_date'),
                    "Liczba stron": d_main.get('number_of_pages') or d_details.get('number_of_pages'),
                    "Opis/Notatki": str(d_main.get('notes', d_details.get('notes', ""))),
                    "Tematy (Subjects)": get_clean_list('subjects'),
                    "Miejsca (Subject Places)": get_clean_list('subject_place') or get_clean_list('subject_places'),
                    "Czasy (Subject Times)": get_clean_list('subject_time') or get_clean_list('subject_times'),
                    "Języki": ", ".join([l.get('key', '').split('/')[-1] for l in d_details.get('languages', [])]),
                    "Klasyfikacja LC": ", ".join(d_details.get('lc_classifications', [])),
                    "ISBN-10": ", ".join(d_details.get('isbn_10', [])),
                    "LCCN": ", ".join(d_details.get('lccn', [])),
                    "OCLC": ", ".join(d_details.get('oclc_numbers', [])),
                    "Link do okładki (L)": cover_url,
                    "Źródło": "Open Library Deep Fix"
                }
    except:
        pass
    return None

# --- UI ---

st.title("🥃 Sunnyvale Deep Scan (No Subtitle + Cover Fix)")
st.markdown("Skrypt zoptymalizowany pod kątem wyciągania zdjęć i pomijania zbędnych podtytułów.")

file = st.file_uploader("Wgraj Excel", type=["xlsx"])
if file:
    df_in = pd.read_excel(file)
    col = st.selectbox("Wybierz kolumnę z ISBN:", df_in.columns)
    
    if st.button("🚀 Start"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        # Cytat
        st.markdown(f'<div class="quote-box">{random.choice(CYTATY_CHLOPAKI)}</div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            isbn = row[col]
            status.text(f"Sprawdzam: {isbn}...")
            
            data = fetch_book_data_v3(isbn)
            
            res_row = {"EAN wejściowy": isbn}
            headers = [
                "Tytuł", "Autorzy", "Wydawcy", "Miejsca wydania", 
                "Kraj wydania", "Data publikacji", "Liczba stron", 
                "Opis/Notatki", "Tematy (Subjects)", "Miejsca (Subject Places)", 
                "Czasy (Subject Times)", "Języki", "Klasyfikacja LC", "ISBN-10", 
                "LCCN", "OCLC", "Link do okładki (L)"
            ]
            
            for h in headers:
                if data and h in data:
                    res_row[h] = data[h]
                else:
                    res_row[h] = "Brak danych"
            
            results.append(res_row)
            bar.progress((i + 1) / len(df_in))
            time.sleep(0.2)

        df_res = pd.DataFrame(results)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        st.download_button("📥 Pobierz finalne wyniki", buf.getvalue(), "sunnyvale_results_final.xlsx")
        st.dataframe(df_res)
