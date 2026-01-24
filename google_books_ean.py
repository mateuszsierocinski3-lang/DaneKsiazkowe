import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="Sunnyvale ISBN-13 Deep Scan", page_icon="🥃")

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

# --- FINALNA LOGIKA (ISBN-13 + FIX OKŁADKI + BRAK PODTYTUŁU) ---

def fetch_book_data_final(isbn):
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
                d_idents = d_details.get('identifiers', {})
                
                # 1. Tytuł i Autorzy (Fallback)
                title = d_main.get('title') or d_details.get('title')
                authors_list = d_main.get('authors') or d_details.get('authors')
                authors = ", ".join([a.get('name', 'Nieznany') for a in authors_list]) if authors_list else "Nieznany"

                # 2. ISBN-13 (Pobieranie z wielu miejsc w JSON)
                isbn13_list = d_details.get('isbn_13') or d_idents.get('isbn_13') or []
                isbn13 = ", ".join(isbn13_list) if isbn13_list else "Brak"

                # 3. Fix Okładki (L)
                cover_url = "Brak okładki"
                if res[key].get('thumbnail_url'):
                    cover_url = res[key].get('thumbnail_url').replace("-S.jpg", "-L.jpg").replace("-M.jpg", "-L.jpg")
                elif d_main.get('cover', {}).get('large'):
                    cover_url = d_main.get('cover', {}).get('large')
                elif d_details.get('covers'):
                    cid = d_details.get('covers')[0]
                    if cid and cid != -1:
                        cover_url = f"https://covers.openlibrary.org/b/id/{cid}-L.jpg"

                # Funkcja do list (Subjects, Places itp.)
                def get_clean_list(field_name):
                    data = d_main.get(field_name) or d_details.get(field_name) or []
                    if not data: return ""
                    if isinstance(data, list):
                        if len(data) > 0 and isinstance(data[0], dict):
                            return ", ".join([x.get('name', str(x)) for x in data])
                        return ", ".join([str(x) for x in data])
                    return str(data)

                return {
                    "Tytuł": title,
                    "Autorzy": authors,
                    "ISBN-13 (z bazy)": isbn13,
                    "ISBN-10": ", ".join(d_details.get('isbn_10', []) or d_idents.get('isbn_10', [])),
                    "Wydawcy": get_clean_list('publishers'),
                    "Miejsca wydania": get_clean_list('publish_places') or get_clean_list('publish_place'),
                    "Data publikacji": d_main.get('publish_date') or d_details.get('publish_date'),
                    "Liczba stron": d_main.get('number_of_pages') or d_details.get('number_of_pages'),
                    "Opis/Notatki": str(d_main.get('notes', d_details.get('notes', ""))),
                    "Tematy (Subjects)": get_clean_list('subjects'),
                    "Miejsca (Subject Places)": get_clean_list('subject_place') or get_clean_list('subject_places'),
                    "Link do okładki (L)": cover_url,
                    "LCCN": ", ".join(d_details.get('lccn', []) or d_idents.get('lccn', [])),
                    "OCLC": ", ".join(d_details.get('oclc_numbers', []) or d_idents.get('oclc', [])),
                    "Źródło": "Open Library Deep Export"
                }
    except:
        pass
    return None

# --- UI STREAMLIT ---

st.title("🥃 Sunnyvale Deep Scan: ISBN-13 Edition")
st.markdown("Skrypt wyciąga ISBN-13, ISBN-10 i wszystkie głębokie dane bez podtytułów.")

file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])
if file:
    df_in = pd.read_excel(file)
    col = st.selectbox("Wybierz kolumnę z Twoim EAN/ISBN:", df_in.columns)
    
    if st.button("🚀 Rozpocznij skanowanie"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        st.markdown(f'<div class="quote-box">{random.choice(CYTATY_CHLOPAKI)}</div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            ean_in = row[col]
            status.text(f"Pobieram dane dla: {ean_in}...")
            
            data = fetch_book_data_final(ean_in)
            
            res_row = {"EAN z pliku": ean_in}
            # Nowy zestaw nagłówków z ISBN-13 na początku
            headers = [
                "Tytuł", "Autorzy", "ISBN-13 (z bazy)", "ISBN-10", "Wydawcy", 
                "Miejsca wydania", "Data publikacji", "Liczba stron", 
                "Opis/Notatki", "Tematy (Subjects)", "Miejsca (Subject Places)", 
                "Link do okładki (L)", "LCCN", "OCLC"
            ]
            
            for h in headers:
                if data and h in data:
                    res_row[h] = data[h]
                else:
                    res_row[h] = "Brak"
            
            results.append(res_row)
            bar.progress((i + 1) / len(df_in))
            time.sleep(0.2)

        df_res = pd.DataFrame(results)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.success("✅ Gotowe! Wszystko na paki.")
        st.download_button("📥 Pobierz Excel z ISBN-13 i okładkami", buf.getvalue(), "sunnyvale_isbn13_final.xlsx")
        st.dataframe(df_res)
