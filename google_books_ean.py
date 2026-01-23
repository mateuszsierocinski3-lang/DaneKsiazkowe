import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import random

# --- KONFIGURACJA ---
st.set_page_config(page_title="Book Scraper Pro", page_icon="📚")

CYTATY_HRABIEGO = [
    "Czekać i mieć nadzieję.",
    "Mądrość ludzka zawiera się w tych dwóch słowach: Czekać i mieć nadzieję!",
    "Historia świata to tylko zbiór anegdot, które sobie ludzie opowiadają.",
    "Jestem tym, kim jestem: narzędziem w rękach Boga.",
    "Litość jest uczuciem, które najbardziej upodabnia człowieka do Boga."
]

# --- STYLIZACJA CSS (Animacja i Cytat) ---
st.markdown("""
<style>
    .book-container { display: flex; flex-direction: column; align-items: center; padding: 20px; }
    .book { width: 60px; height: 45px; position: relative; perspective: 150px; margin-bottom: 20px; }
    .page { width: 30px; height: 45px; background: white; border: 2px solid #333; position: absolute; right: 0; transform-origin: left; animation: flip 1.2s infinite linear; border-radius: 0 2px 2px 0; }
    .page:nth-child(2) { animation-delay: 0.4s; }
    .page:nth-child(3) { animation-delay: 0.8s; }
    @keyframes flip { 0% { transform: rotateY(0deg); } 100% { transform: rotateY(-180deg); } }
    .book::before { content: ''; position: absolute; width: 30px; height: 45px; background: #eee; border: 2px solid #333; left: 0; border-radius: 2px 0 0 2px; }
    .quote-box { text-align: center; font-family: 'Georgia', serif; font-style: italic; color: #555; background: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #0e1117; max-width: 500px; }
</style>
""", unsafe_allow_html=True)

# --- LOGIKA NAPRAWCZA EAN ---
def get_ean_variants(ean):
    """Naprawia błędy Excela i tworzy listę wariantów do sprawdzenia."""
    if pd.isna(ean): return []
    # Usunięcie .0 i formatu naukowego
    s = str(ean).strip()
    if 'E' in s.upper() or '.' in s:
        try: s = "{:.0f}".format(float(ean))
        except: pass
    ean_clean = re.sub(r'\D', '', s)
    if not ean_clean: return []
    
    variants = [ean_clean]
    if len(ean_clean) == 12: variants.append("0" + ean_clean) # Brakujące zero na początku
    if len(ean_clean) > 10: variants.append(ean_clean[-10:])  # Wersja 10-cyfrowa
    return list(dict.fromkeys(variants))

# --- POBIERANIE DANYCH ---
def fetch_all_data(ean_original):
    variants = get_ean_variants(ean_original)
    final_data = None
    
    # 1. Google Books (Priorytet)
    for v in variants:
        try:
            res = requests.get(f"https://www.googleapis.com/books/v1/volumes?q=isbn:{v}", timeout=10)
            if res.status_code == 200 and 'items' in res.json():
                info = res.json()['items'][0]['volumeInfo']
                ids = info.get('industryIdentifiers', [])
                img = info.get('imageLinks', {})
                
                final_data = {
                    "ISBN-13": next((i['identifier'] for i in ids if i['type'] == 'ISBN_13'), "Brak"),
                    "ISBN-10": next((i['identifier'] for i in ids if i['type'] == 'ISBN_10'), "Brak"),
                    "Tytuł": info.get('title', "Brak danych"),
                    "Autor": ", ".join(info.get('authors', [])),
                    "Współtwórca": "", # Google rzadko to rozdziela
                    "Wydawca": info.get('publisher', ""),
                    "Opis": info.get('description', "Brak opisu"),
                    "Opublikowane": info.get('publishedDate', "Brak"),
                    "Liczba stron": info.get('pageCount', "Brak"),
                    "Link do okładki": (img.get('thumbnail') or "").replace("http://", "https://"),
                    "Źródło": "Google"
                }
                break
        except: continue

    # 2. Fallback: Biblioteka Narodowa (Tylko Wydawca jeśli brak)
    if not final_data or not final_data.get("Wydawca"):
        for v in variants:
            try:
                bn_res = requests.get(f"https://data.bn.org.pl/api/institutions/bibs.json?isbnIssn={v}", timeout=10)
                if bn_res.status_code == 200:
                    bibs = bn_res.json().get('bibs', [])
                    if bibs:
                        if not final_data:
                            final_data = {k: "Nie znaleziono" for k in ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]}
                            final_data["Tytuł"] = bibs[0].get('title', "Nie znaleziono")
                        final_data["Wydawca"] = bibs[0].get('publisher', "Nie znaleziono")
                        final_data["Źródło"] = "BN"
                        break
            except: continue

    return final_data

# --- INTERFEJS ---
st.title("📚 ISBN Multibaza Scraper")
uploaded_file = st.file_uploader("Wgraj plik Excel", type=["xlsx"])

if uploaded_file:
    df_input = pd.read_excel(uploaded_file)
    col_name = st.selectbox("Wybierz kolumnę EAN:", df_input.columns)
    
    if st.button("🚀 Przetwarzaj"):
        results = []
        progress = st.progress(0)
        status = st.empty()
        
        # Animacja i cytat
        anim_placeholder = st.empty()
        anim_placeholder.markdown(f"""
            <div class="book-container">
                <div class="book"><div class="page"></div><div class="page"></div><div class="page"></div></div>
                <div class="quote-box">"{random.choice(CYTATY_HRABIEGO)}"<br><small>— Hrabia Monte Christo</small></div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in df_input.iterrows():
            ean = row[col_name]
            status.text(f"Przetwarzam: {ean} ({i+1}/{len(df_input)})")
            
            data = fetch_all_data(ean)
            
            # Mapowanie do struktury zgodnej z Twoim plikiem
            entry = {"EAN z pliku": ean}
            columns_order = ["ISBN-13", "ISBN-10", "Tytuł", "Autor", "Współtwórca", "Wydawca", "Opis", "Opublikowane", "Liczba stron", "Link do okładki", "Źródło"]
            
            for col in columns_order:
                entry[col] = data.get(col, "Nie znaleziono") if data else "Nie znaleziono"
            
            results.append(entry)
            progress.progress((i + 1) / len(df_input))
            time.sleep(0.1)

        anim_placeholder.empty()
        status.success("✅ Gotowe!")
        
        df_final = pd.DataFrame(results)
        
        # Export
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button("📥 Pobierz wynikowy Excel", buf.getvalue(), "wynik_multibaza.xlsx", "application/vnd.ms-excel")
        st.dataframe(df_final)
