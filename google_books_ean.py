import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="Open Library & Sunnyvale Scraper", page_icon="🥃")

# --- CYTATY Z CHŁOPAKÓW Z BARAKÓW ---
CYTATY_CHLOPAKI = [
    "„To nie jest żadne rocket appliances.” — Ricky",
    "„Miałem wtedy z dziesięć lat i miałem tylko jedno marzenie: być wozem asenizacyjnym.” — Ricky",
    "„Julian, on pije wodę z psem! To jest obrzydliwe!” — Bubbles",
    "„Czujesz to? To gówniany wiatr wieje.” — Jim Lahey",
    "„Jeden gram haszyszu to jeden gram haszyszu. Nie możesz powiedzieć, że to nie jest gram haszyszu.” — Ricky",
    "„Przyjaciele to ludzie, którzy pomagają ci kraść benzynę, kiedy nie masz na nią pieniędzy.” — Ricky",
    "„Zasady są proste: nie jesz moich pepperoni i nie pijesz mojego soku.” — Ricky",
    "„Życie nie polega tylko na ćpaniu i piciu, Julian. Trzeba jeszcze kraść.” — Ricky"
]

# --- STYLE CSS ---
st.markdown("""
<style>
    .book-container { display: flex; flex-direction: column; align-items: center; padding: 20px; }
    .book { width: 60px; height: 45px; position: relative; perspective: 150px; margin-bottom: 20px; }
    .page { width: 30px; height: 45px; background: #e0e0e0; border: 2px solid #333; position: absolute; right: 0; transform-origin: left; animation: flip 1.2s infinite linear; border-radius: 0 2px 2px 0; }
    @keyframes flip { 0% { transform: rotateY(0deg); } 100% { transform: rotateY(-180deg); } }
    .quote-box { text-align: center; font-family: 'Courier New', Courier, monospace; font-weight: bold; color: #1a1a1a; background: #fdfd96; padding: 20px; border-radius: 10px; border: 3px solid #333; box-shadow: 5px 5px 0px #000; max-width: 600px; }
</style>
""", unsafe_allow_html=True)

# --- FUNKCJE POMOCNICZE ---

def clean_html(text):
    if not text: return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', str(text))

def get_ean_variants(ean_raw):
    s = re.sub(r'\D', '', str(ean_raw))
    if not s: return []
    v = [s]
    if s.startswith('0'): v.append(s[1:])
    if len(s) == 12: v.append('0' + s)
    if len(s) >= 10: v.append(s[-10:])
    return list(dict.fromkeys(v))

def fetch_open_library(variants):
    """Odpytuje wyłącznie Open Library."""
    for e in variants:
        try:
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{e}&format=json&jscmd=data"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                key = f"ISBN:{e}"
                if key in data:
                    book = data[key]
                    return {
                        "Tytuł": book.get('title', "Brak tytułu"),
                        "Autor": ", ".join([a['name'] for a in book.get('authors', [])]) if 'authors' in book else "Nieznany",
                        "Wydawca": ", ".join([p['name'] for p in book.get('publishers', [])]) if 'publishers' in book else "Brak danych",
                        "Opis": clean_html(book.get('notes', "Brak opisu w Open Library")),
                        "Opublikowane": book.get('publish_date', "Brak daty"),
                        "Link do okładki": book.get('cover', {}).get('large', ""),
                        "Źródło": "Open Library"
                    }
        except:
            continue
    return None

# --- UI APLIKACJI ---

st.title("🥃 Sunnyvale ISBN Scanner (Open Library Edition)")
st.markdown("*„Dobra, Julian, sprawdzamy te książki, ale potem idziemy na cheeseburgery.”*")

file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if file:
    df_in = pd.read_excel(file)
    col = st.selectbox("Wybierz kolumnę z ISBN:", df_in.columns)
    
    if st.button("🚀 Odpal silnik (Cory, Trevor, fajki już!)"):
        final_results = []
        bar = st.progress(0)
        status = st.empty()
        anim = st.empty()
        
        # Animacja i cytat z Baraków
        wybrany_cytat = random.choice(CYTATY_CHLOPAKI)
        anim.markdown(f"""
            <div class="book-container">
                <div class="book"><div class="page"></div></div>
                <div class="quote-box">{wybrany_cytat}</div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            isbn_raw = row[col]
            status.text(f"Przeszukuję baraki dla ISBN: {isbn_raw}...")
            
            # Resetowanie danych - to zapobiega powielaniu Julesa Verne'a!
            vars_to_check = get_ean_variants(isbn_raw)
            book_info = fetch_open_library(vars_to_check)
            
            # Budowa rekordu - jeśli nic nie znajdzie, wpisze "Brak w baraku"
            record = {"EAN z pliku": isbn_raw}
            headers = ["Tytuł", "Autor", "Wydawca", "Opis", "Opublikowane", "Link do okładki", "Źródło"]
            
            for h in headers:
                if book_info and h in book_info:
                    record[h] = book_info[h]
                else:
                    record[h] = "Brak w baraku"
            
            final_results.append(record)
            bar.progress((i + 1) / len(df_in))
            time.sleep(0.2) # Open Library jest w porządku, nie trzeba długo czekać

        anim.empty()
        status.success("✅ Gotowe! Wszystkie książki przemycone do Excela.")
        
        df_res = pd.DataFrame(final_results)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.download_button("📥 Pobierz wyniki z baraków", buf.getvalue(), "chlopaki_z_barakow_results.xlsx")
        st.dataframe(df_res)
