import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import time

# --- KONFIGURACJA ---
st.set_page_config(page_title="Bibliotekarz AI", page_icon="📖")

# --- KLUCZ API ---
# UWAGA: Wklej swój klucz między cudzysłowy poniżej!
API_KEY = "AIzaSyAng8dcG9iUIQ6L2H5iK7QuHkiPSovJ3eU" 

# --- FUNKCJA AI ---
def fetch_book_data(query):
    try:
        # Konfiguracja wewnątrz funkcji, aby uniknąć błędów przy starcie
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"Podaj dane książki: {query}. Odpowiedz TYLKO JSONEM: {{\"Tytuł\":\"\", \"Autorzy\":\"\", \"Opis\":\"\"}}"
        response = model.generate_content(prompt)
        
        # Czyszczenie odpowiedzi z formatowania Markdown (```json ... ```)
        text = response.text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        
        return json.loads(text)
    except Exception as e:
        st.error(f"Szczegóły błędu dla {query}: {e}")
        return None

# --- INTERFEJS ---
st.title("📚 Bibliotekarz AI")

# Sprawdzenie czy klucz został zmieniony
if "AIza" not in API_KEY:
    st.error("❌ Musisz wpisać poprawny klucz API w kodzie (linia 12)!")

uploaded_file = st.file_uploader("1. Załaduj plik Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("2. Wybierz kolumnę z ISBN lub Tytułem:", df_in.columns)
    
    # PRZYCISK - teraz jest widoczny zawsze po wgraniu pliku
    if st.button("3. URUCHOM KATALOGOWANIE"):
        final_results = []
        progress_bar = st.progress(0)
        status_msg = st.empty()
        
        for i, row in df_in.iterrows():
            q = str(row[target_col])
            status_msg.info(f"Szukam: {q} ({i+1}/{len(df_in)})")
            
            res = fetch_book_data(q)
            
            entry = {"Szukana fraza": q}
            if res:
                entry["Tytuł"] = res.get("Tytuł", "Brak")
                entry["Autorzy"] = res.get("Autorzy", "Brak")
                entry["Opis"] = res.get("Opis", "Brak")
            else:
                entry["Tytuł"] = "Błąd"
                entry["Autorzy"] = "Błąd"
                entry["Opis"] = "Błąd"
                
            final_results.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            time.sleep(1.5) # Ważne dla darmowego limitu
            
        st.session_state.final_df = pd.DataFrame(final_results)
        status_msg.success("✅ Gotowe!")

# --- WYŚWIETLANIE WYNIKÓW ---
if 'final_df' in st.session_state:
    st.divider()
    st.dataframe(st.session_state.final_df)
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.final_df.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Pobierz wynikowy Excel",
        data=buf.getvalue(),
        file_name="katalog_ai.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
