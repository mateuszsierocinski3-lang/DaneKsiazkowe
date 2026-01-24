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

# --- POPRAWIONA LOGIKA POBIERANIA ---

def fetch_book_data_v2(isbn):
    isbn_clean = re.sub(r'\D', '', str(isbn))
    if not isbn_clean: return None
    
    # Próbujemy pobrać dane najszerszym możliwym zapytaniem
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=details"
    
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            res = r.json()
            key = f"ISBN:{isbn_clean}"
            if key in res:
                # Wyciągamy obie sekcje
                d_main = res[key].get('data', {})
                d_details = res[key].get('details', {})
                
                # Inteligentne łączenie: bierzemy z 'data', a jeśli puste - z 'details'
                title = d_main.get('title') or d_details.get('title')
                
                # Autorzy często są w różnych miejscach lub formatach
                authors_list = d_main.get('authors') or d_details.get('authors')
                authors = "Nieznany"
                if authors_list:
                    authors = ", ".join([a.get('name', 'Nieznany') for a in authors_list])

                # Tematy, Miejsca, Czasy - Open Library często ma je w 'details' jako zwykłe listy stringów
                def get_list_or_dicts(field_name):
                    data = d_main.get(field_name) or d_details.get(field_name) or []
                    if not data: return ""
                    if isinstance(data[0], dict):
                        return ", ".join([x.get('name', str(x)) for x in data])
                    return ", ".join([str(x) for x in data])

                return {
                    "Tytuł": title,
                    "Podtytuł": d_main.get('subtitle') or d_details.get('subtitle', ""),
                    "Autorzy": authors,
                    "Wydawcy": get_list_or_dicts('publishers'),
                    "Miejsca wydania": get_list_or_dicts('publish_places') or get_list_or_dicts('publish_place'),
                    "Kraj wydania": d_details.get('publish_country', ""),
                    "Data publikacji": d_main.get('publish_date') or d_details.get('publish_date'),
                    "Liczba stron": d_main.get('number_of_pages') or d_details.get('number_of_pages'),
                    "Opis/Notatki": str(d_main.get('notes', d_details.get('notes', ""))),
                    "Tematy (Subjects)": get_list_or_dicts('subjects'),
                    "Miejsca (Subject Places)": get_list_or_dicts('subject_place') or get_list_or_dicts('subject_places'),
                    "Czasy (Subject Times)": get_list_or_dicts('subject_time') or get_list_or_dicts('subject_times'),
                    "Języki": ", ".join([l.get('key', '').split('/')[-1] for l in d_details.get('languages', [])]),
                    "Klasyfikacja LC": ", ".join(d_details.get('lc_classifications', [])),
                    "ISBN-10": ", ".join(d_details.get('isbn_10', [])),
                    "LCCN": ", ".join(d_details.get('lccn', [])),
                    "OCLC": ", ".join(d_details.get('oclc_numbers', [])),
                    "Link do okładki (L)": d_main.get('cover', {}).get('large', ""),
                    "Źródło": "OL Deep v2"
                }
    except:
        pass
    return None

# --- UI ---

st.title("🥃 Sunnyvale Deep Scan FIX")
st.markdown("Poprawiona wersja wyciągająca dane ukryte głęboko w strukturze JSON.")

file = st.file_uploader("Wgraj Excel", type=["xlsx"])
if file:
    df_in = pd.read_excel(file)
    col = st.selectbox("Kolumna ISBN:", df_in.columns)
    
    if st.button("🚀 Start"):
        results = []
        bar = st.progress(0)
        quote = st.empty()
        quote.markdown(f'<div class="quote-box">{random.choice(CYTATY_CHLOPAKI)}</div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            isbn = row[col]
            data = fetch_book_data_v2(isbn)
            
            res_row = {"EAN wejściowy": isbn}
            headers = [
                "Tytuł", "Podtytuł", "Autorzy", "Wydawcy", "Miejsca wydania", 
                "Kraj wydania", "Data publikacji", "Liczba stron", 
                "Opis/Notatki", "Tematy (Subjects)", "Miejsca (Subject Places)", 
                "Czasy (Subject Times)", "Języki", "Klasyfikacja LC", "ISBN-10", 
                "LCCN", "OCLC", "Link do okładki (L)"
            ]
            
            for h in headers:
                res_row[h] = data.get(h, "Brak") if data else "Nie znaleziono"
            
            results.append(res_row)
            bar.progress((i + 1) / len(df_in))
            time.sleep(0.2)

        df_res = pd.DataFrame(results)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        st.download_button("📥 Pobierz poprawione dane", buf.getvalue(), "naprawione_wyniki.xlsx")
        st.dataframe(df_res)
