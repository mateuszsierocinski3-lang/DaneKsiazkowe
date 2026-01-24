import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="Sunnyvale AI-Description Scraper", page_icon="🥃")

CYTATY_CHLOPAKI = [
    "„To nie jest żadne rocket appliances.” — Ricky",
    "„Zasady są proste: nie jesz moich pepperoni i nie pijesz mojego soku.” — Ricky",
    "„Czujesz to? To gówniany wiatr wieje.” — Jim Lahey",
    "„Julian, on pije wodę z psem! To jest obrzydliwe!” — Bubbles"
]

# --- FUNKCJA GENERUJĄCA OPIS (Gdy brak w bazie) ---
def generate_fallback_description(title, authors, subjects):
    if not title or title == "Brak":
        return "Brak wystarczających danych do wygenerowania opisu."
    
    desc = f"Książka pt. '{title}', której autorem jest {authors if authors != 'Nieznany' else 'zespół ekspertów'}."
    if subjects and subjects != "Brak":
        main_subject = subjects.split(',')[0]
        desc += f" Pozycja ta porusza zagadnienia z zakresu: {main_subject.lower()}."
    
    desc += " Jest to cenne źródło wiedzy dla czytelników poszukujących rzetelnych informacji w tej tematyce."
    return desc

# --- LOGIKA POBIERANIA ---
def fetch_book_data_ai(isbn):
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
                
                title = d_main.get('title') or d_details.get('title') or "Brak"
                authors_list = d_main.get('authors') or d_details.get('authors')
                authors = ", ".join([a.get('name', 'Nieznany') for a in authors_list]) if authors_list else "Nieznany"
                
                def get_clean_list(field_name):
                    data = d_main.get(field_name) or d_details.get(field_name) or []
                    if isinstance(data, list) and data:
                        if isinstance(data[0], dict): return ", ".join([x.get('name', str(x)) for x in data])
                        return ", ".join([str(x) for x in data])
                    return "Brak"

                subjects = get_clean_list('subjects')
                
                # POBIERANIE LUB GENEROWANIE OPISU
                raw_notes = d_main.get('notes') or d_details.get('notes', "")
                if isinstance(raw_notes, dict): raw_notes = raw_notes.get('value', "")
                
                if not raw_notes or len(str(raw_notes)) < 10:
                    description = generate_fallback_description(title, authors, subjects)
                    source_desc = "Wygenerowany (AI Fallback)"
                else:
                    description = str(raw_notes)
                    source_desc = "Baza Open Library"

                # Okładka
                cover_url = "Brak okładki"
                if res[key].get('thumbnail_url'):
                    cover_url = res[key].get('thumbnail_url').replace("-S.jpg", "-L.jpg").replace("-M.jpg", "-L.jpg")
                elif d_details.get('covers'):
                    cid = d_details.get('covers')[0]
                    if cid and cid != -1: cover_url = f"https://covers.openlibrary.org/b/id/{cid}-L.jpg"

                return {
                    "Tytuł": title,
                    "Autorzy": authors,
                    "Opis": description,
                    "Źródło Opisu": source_desc,
                    "ISBN-13": ", ".join(d_details.get('isbn_13', []) or d_idents.get('isbn_13', [])),
                    "Wydawcy": get_clean_list('publishers'),
                    "Data publikacji": d_main.get('publish_date') or d_details.get('publish_date'),
                    "Tematy (Subjects)": subjects,
                    "Link do okładki (L)": cover_url
                }
    except: pass
    return None

# --- UI ---
st.title("🥃 Sunnyvale AI-Description Scraper")
st.markdown("Ten skrypt nie tylko kradnie dane, ale też sam pisze opisy, jak ich nie ma!")

file = st.file_uploader("Wgraj Excel", type=["xlsx"])
if file:
    df_in = pd.read_excel(file)
    col = st.selectbox("Wybierz kolumnę z ISBN:", df_in.columns)
    
    if st.button("🚀 Start (Daj mi to!)"):
        results = []
        bar = st.progress(0)
        st.info(random.choice(CYTATY_CHLOPAKI))

        for i, row in df_in.iterrows():
            isbn = row[col]
            data = fetch_book_data_ai(isbn)
            
            res_row = {"EAN wejściowy": isbn}
            headers = ["Tytuł", "Autorzy", "Opis", "Źródło Opisu", "ISBN-13", "Wydawcy", "Data publikacji", "Link do okładki (L)"]
            
            for h in headers:
                res_row[h] = data.get(h, "Brak") if data else "Nie znaleziono"
            
            results.append(res_row)
            bar.progress((i + 1) / len(df_in))
            time.sleep(0.1)

        df_res = pd.DataFrame(results)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        st.download_button("📥 Pobierz dane z opisami", buf.getvalue(), "sunnyvale_ai_descriptions.xlsx")
        st.dataframe(df_res)
