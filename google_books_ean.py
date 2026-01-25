import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz - Zaawansowany Skaner ISBN", page_icon="📖")

# --- CYTATY ---
CYTATY_LITERACKIE = [
    "„Czekać i pokładać nadzieję!” — Aleksander Dumas, Hrabia Monte Christo",
    "„Wiedza to jedyny skarb, którego nie można ukraść, a który dzieli się bez uszczerbku.” — Aleksander Dumas",
    "„Pod tą maską kryje się coś więcej niż ciało. Pod tą maską kryje się idea, a idee są kuloodporne.” — Alan Moore, V jak Vendetta",
    "„Naród nie powinien bać się swojego rządu. To rząd powinien bać się swojego narodu.” — Alan Moore, V jak Vendetta",
    "„Szczęście jest jak te pałace z bajek, których strzegą smoki. Trzeba walczyć, by je zdobyć.” — Aleksander Dumas",
    "„Wszyscy jesteśmy sprawcami własnego losu.” — Aleksander Dumas"
]

# --- ANIMACJA I STYLE ---
st.markdown("""
<style>
    /* Animacja przewracanej książki */
    .book {
      position: relative;
      border: 5px solid #2c3e50;
      width: 60px;
      height: 45px;
      margin: 20px auto;
    }
    .book__page {
      position: absolute;
      left: 50%;
      top: 0;
      width: 50%;
      height: 100%;
      background: #ecf0f1;
      transform-origin: left center;
      animation: flip 1.5s infinite linear;
      border-left: 1px solid #bdc3c7;
    }
    .book__page:nth-child(1) { animation-delay: 0s; }
    .book__page:nth-child(2) { animation-delay: 0.5s; }
    .book__page:nth-child(3) { animation-delay: 1s; }

    @keyframes flip {
      0% { transform: rotateY(0deg); }
      100% { transform: rotateY(-180deg); }
    }

    .quote-box {
        text-align: center;
        font-style: italic;
        font-family: 'Georgia', serif;
        color: #2c3e50;
        background: #fdfcf0;
        padding: 25px;
        border-left: 5px solid #e67e22;
        margin: 20px 0;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- LOGIKA GENEROWANIA OPISÓW ---
def generate_fallback_description(title, authors, subjects):
    if not title or title == "Brak":
        return "Brak danych wejściowych do analizy treści."
    
    desc = f"Dzieło literackie pt. '{title}', stworzone przez autora: {authors if authors != 'Nieznany' else 'anonimowy twórca'}."
    if subjects and subjects != "Brak":
        main_subject = subjects.split(',')[0].strip()
        desc += f" Treść publikacji koncentruje się wokół tematyki: {main_subject.lower()}."
    desc += " Pozycja stanowi istotny wkład w dany nurt literacki lub naukowy, oferując czytelnikowi pogłębioną perspektywę."
    return desc

# --- LOGIKA POBIERANIA DANYCH ---
def fetch_bibliotekarz_data(isbn):
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
                
                # Opis / Fallback
                raw_notes = d_main.get('notes') or d_details.get('notes', "")
                if isinstance(raw_notes, dict): raw_notes = raw_notes.get('value', "")
                
                if not raw_notes or len(str(raw_notes)) < 15:
                    description = generate_fallback_description(title, authors, subjects)
                    source_desc = "Wygenerowany autorsko"
                else:
                    description = str(raw_notes).strip()
                    source_desc = "Baza Biblioteczna"

                # Okładka High-Res
                cover_url = "Brak okładki"
                if res[key].get('thumbnail_url'):
                    cover_url = res[key].get('thumbnail_url').replace("-S.jpg", "-L.jpg").replace("-M.jpg", "-L.jpg")
                elif d_details.get('covers'):
                    cid = d_details.get('covers')[0]
                    if cid and cid != -1: cover_url = f"https://covers.openlibrary.org/b/id/{cid}-L.jpg"

                return {
                    "Tytuł": title,
                    "Autorzy": authors,
                    "Krótki Opis": description,
                    "Źródło Opisu": source_desc,
                    "ISBN-13": ", ".join(d_details.get('isbn_13', []) or d_idents.get('isbn_13', [])),
                    "ISBN-10": ", ".join(d_details.get('isbn_10', []) or d_idents.get('isbn_10', [])),
                    "Wydawcy": get_clean_list('publishers'),
                    "Data publikacji": d_main.get('publish_date') or d_details.get('publish_date'),
                    "Tematy": subjects,
                    "Link do okładki (L)": cover_url
                }
    except: pass
    return None

# --- UI STREAMLIT ---
st.title("📖 Bibliotekarz")
st.markdown("### *System głębokiej analizy i katalogowania zbiorów*")

file = st.file_uploader("Załaduj woluminy do analizy (Excel)", type=["xlsx"])

if file:
    df_in = pd.read_excel(file)
    col = st.selectbox("Wskaż kolumnę z identyfikatorami ISBN:", df_in.columns)
    
    if st.button("Rozpocznij proces skatalogowania"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        # Animacja książki
        st.markdown('<div class="book"><div class="book__page"></div><div class="book__page"></div><div class="book__page"></div></div>', unsafe_allow_html=True)
        
        # Losowy cytat
        st.markdown(f'<div class="quote-box">{random.choice(CYTATY_LITERACKIE)}</div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            isbn_val = row[col]
            status.markdown(f"**Analiza woluminu:** `{isbn_val}`")
            
            data = fetch_bibliotekarz_data(isbn_val)
            
            res_row = {"Identyfikator wejściowy": isbn_val}
            headers = ["Tytuł", "Autorzy", "Krótki Opis", "Źródło Opisu", "ISBN-13", "ISBN-10", "Wydawcy", "Data publikacji", "Link do okładki (L)"]
            
            for h in headers:
                res_row[h] = data.get(h, "Brak danych") if data else "Nie znaleziono w archiwach"
            
            results.append(res_row)
            bar.progress((i + 1) / len(df_in))
            time.sleep(0.15)

        status.success("Proces katalogowania zakończony sukcesem.")
        
        df_res = pd.DataFrame(results)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.download_button("📥 Pobierz kompletny rejestr (Excel)", buf.getvalue(), "rejestr_bibliotekarza.xlsx")
        st.dataframe(df_res)
