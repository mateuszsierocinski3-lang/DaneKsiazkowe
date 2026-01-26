import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import random
import time

# --- KONFIGURACJA ---
st.set_page_config(page_title="Darmowy Bibliotekarz AI", page_icon="📚", layout="centered")

# --- LOGIKA GEMINI ---
def fetch_book_data_gemini(api_key, query):
    try:
        genai.configure(api_key="AIzaSyAng8dcG9iUIQ6L2H5iK7QuHkiPSovJ3eU")
        model = genai.GenerativeModel('gemini-1.5-flash',
                                      generation_config={"response_mime_type": "application/json"})
        
        prompt = f"""
        Jesteś ekspertem bibliotekarstwa. Na podstawie zapytania: "{query}", znajdź dane książki.
        Zwróć dane w formacie JSON. W polu 'Opis' stwórz bogaty, marketingowy opis książki po polsku.
        
        Struktura JSON:
        {{
            "Tytuł": "...",
            "Autorzy": "...",
            "Liczba stron": "...",
            "Wydawcy": "...",
            "Data publikacji": "...",
            "ISBN-13": "...",
            "ISBN-10": "...",
            "Opis": "...",
            "Tematy": "...",
            "Miejsca wydania": "..."
        }}
        """
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Błąd: {e}")
        return None

# --- UI ---
st.title("📚 Bibliotekarz Gemini (Darmowy)")
st.info("Używasz modelu Google Gemini 1.5 Flash - całkowicie za darmo.")

# Pasek boczny na klucz
api_key = st.sidebar.text_input("Wklej klucz Google API (AIza...):", type="password")
st.sidebar.markdown("[Pobierz klucz tutaj](https://aistudio.google.com/app/apikey)")

uploaded_file = st.file_uploader("Załaduj plik Excel", type=["xlsx"])

if uploaded_file and api_key:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę z ISBN/Tytułem:", df_in.columns)
    
    if st.button("Rozpocznij darmowe skanowanie"):
        final_data = []
        progress_bar = st.progress(0)
        
        for i, row in df_in.iterrows():
            book_query = row[target_col]
            st.write(f"🔍 Przetwarzam: {book_query}")
            
            res = fetch_book_data_gemini(api_key, book_query)
            
            entry = {"Oryginalne zapytanie": book_query}
            headers = ["Tytuł", "Autorzy", "Liczba stron", "Wydawcy", "Data publikacji", "ISBN-13", "Opis", "Tematy"]
            
            for h in headers:
                entry[h] = res.get(h, "Brak danych") if res else "Błąd"
                
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            # Gemini ma limity zapytań na minutę (RPM), mała pauza pomaga
            time.sleep(1) 

        st.session_state.res_df = pd.DataFrame(final_data)
        st.success("Gotowe!")

if 'res_df' in st.session_state:
    df_res = st.session_state.res_df
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        df_res.to_excel(writer, index=False)
    st.download_button("📥 Pobierz darmowy raport Excel", buf.getvalue(), "biblioteka_gemini.xlsx")
    st.dataframe(df_res)
