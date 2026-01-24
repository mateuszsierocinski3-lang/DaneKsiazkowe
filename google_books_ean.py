import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="Open Library Sunnyvale Edition", page_icon="🥃")

# --- CYTATY Z CHŁOPAKÓW Z BARAKÓW ---
CYTATY_CHLOPAKI = [
    "„To nie jest żadne rocket appliances.” — Ricky",
    "„Miałem wtedy z dziesięć lat i miałem tylko jedno marzenie: być wozem asenizacyjnym.” — Ricky",
    "„Julian, on pije wodę z psem! To jest obrzydliwe!” — Bubbles",
    "„Czujesz to? To gówniany wiatr wieje.” — Jim Lahey",
    "„Jeden gram haszyszu to jeden gram haszyszu.” — Ricky",
    "„Przyjaciele to ludzie, którzy pomagają ci kraść benzynę.” — Ricky",
    "„Zasady są proste: nie jesz moich pepperoni i nie pijesz mojego soku.” — Ricky"
]

# --- STYLE CSS ---
st.markdown("""
<style>
    .main-container { display: flex; flex-direction: column; align-items: center; padding: 20px; }
    .quote-box { 
        text-align: center; 
        font-family: 'Courier New', monospace; 
        font-weight: bold; 
        color: #1a1a1a; 
        background: #fdfd96; 
        padding: 20px; 
        border-radius: 10px; 
        border: 3px solid #333; 
        box-shadow: 8px 8px 0px #000;
        margin: 20px 0;
    }
    .stProgress > div > div > div > div { background-color: #333; }
</style>
""", unsafe_allow_html=True)

# --- LOGIKA WYSZUKIWANIA ---

def get_ean_variants(ean_raw):
    """Generuje unikalne warianty numeru do sprawdzenia."""
    s = re.sub(r'\D', '', str(ean_raw))
    if not s: return []
    v = [s]
    if s.startswith('0'): v.append(s[1:])
    if len(s) == 12: v.append('0' + s)
    if len(s) >= 10: v.append(s[-10:])
    return list(dict.fromkeys(v))

def fetch_open_library_read_api(variants):
    """Wykorzystuje Read API (Brief Viewer) Open Library."""
    for isbn in variants:
        try:
            # Używamy sugerowanego przez Ciebie endpointu Read API
            url = f"https://openlibrary.org/api/volumes/brief/isbn/{isbn}.json"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data and 'records' in data:
                    # Pobieramy pierwszy dostępny rekord
                    first_key = list(data['records'].keys())[0]
                    record = data['records'][first_key]
                    
                    # Wyciągamy dane podstawowe z rekordu
                    return {
                        "Tytuł": record.get('data', {}).get('title', "Brak tytułu"),
                        "Autor": ", ".join([a['name'] for a in record.get('data', {}).get('authors', [])]) if record.get('data', {}).get('authors') else "Nieznany",
                        "Wydawca": record.get('data', {}).get('publishers', [{}])[0].get('name', "Brak danych"),
                        "Opublikowane": record.get('data', {}).get('publish_date', "Brak daty"),
                        "Link OL": record.get('recordURL', ""),
                        "Źródło": "Open Library Read API"
                    }
        except:
            continue
    return None

# --- APLIKACJA ---

st.title("🥃 Sunnyvale Book Tracker")
st.markdown("*„Dobra, Cory, Trevor, dawajcie te numery ISBN, tylko szybko!”*")

uploaded_file = st.file_uploader("Wgraj arkusz z baraku (Excel)", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    column = st.selectbox("Wybierz kolumnę z ISBN:", df_in.columns)
    
    if st.button("🚀 Przeszukaj baraki"):
        final_data = []
        progress = st.progress(0)
        status = st.empty()
        quote_area = st.empty()
        
        # Losowy cytat na start
        quote_area.markdown(f'<div class="quote-box">{random.choice(CYTATY_CHLOPAKI)}</div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            raw_val = row[column]
            status.text(f"Sprawdzam towar: {raw_val}...")
            
            # Kluczowe: Szukamy wariantów i pobieramy dane
            # Jeśli funkcja nie znajdzie nic, zwróci None, co wyczyści wynik dla tego wiersza
            variants = get_ean_variants(raw_val)
            book_info = fetch_open_library_read_api(variants)
            
            # Budowa czystego rekordu dla każdego wiersza
            entry = {"EAN wejściowy": raw_val}
            fields = ["Tytuł", "Autor", "Wydawca", "Opublikowane", "Link OL", "Źródło"]
            
            for f in fields:
                if book_info and f in book_info:
                    entry[f] = book_info[f]
                else:
                    entry[f] = "Brak w baraku"
            
            final_data.append(entry)
            progress.progress((i + 1) / len(df_in))
            
            # Małe opóźnienie dla stabilności
            time.sleep(0.1)

        status.success("✅ Skończone. Julian, bierz drina, mamy to.")
        quote_area.empty()
        
        # Generowanie pliku wynikowego
        df_res = pd.DataFrame(final_data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Pobierz wyniki przemytu",
            data=buffer.getvalue(),
            file_name="wyniki_sunnyvale_ol.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.dataframe(df_res)
