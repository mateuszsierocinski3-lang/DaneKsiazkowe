import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import random
import time

# --- KONFIGURACJA ---
st.set_page_config(page_title="Darmowy Bibliotekarz AI", page_icon="📚", layout="centered")

# --- KLUCZ API I KONFIGURACJA MODELU ---
# WKLEJ SWÓJ KLUCZ PONIŻEJ:
API_KEY = "AIzaSy..." 

genai.configure(api_key=API_KEY)

# Ustawienie modelu - używamy wersji 'latest' dla lepszej kompatybilności
generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-latest",
    generation_config=generation_config,
)

# --- LOGIKA POBIERANIA DANYCH ---
def fetch_book_data_gemini(query):
    try:
        prompt = f"""
        Jesteś ekspertem bibliotekarstwa. Na podstawie zapytania: "{query}", znajdź dane książki.
        Zwróć dane w formacie JSON. W polu 'Opis' stwórz bogaty, merytoryczny i marketingowy opis książki po polsku.
        
        Wymagany format JSON:
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
        Jeśli nie znasz jakiejś danej, wpisz "Brak".
        """
        response = model.generate_content(prompt)
        # Parsowanie tekstu na słownik Pythona
        return json.loads(response.text)
    except Exception as e:
        # Wyświetlamy błąd tylko w konsoli, aby nie psuć tabeli użytkownikowi
        print(f"Błąd przy {query}: {e}")
        return None

# --- UI APLIKACJI ---
st.title("📚 Bibliotekarz Gemini")
st.subheader("Darmowe Katalogowanie AI")

uploaded_file = st.file_uploader("Załaduj plik Excel (xlsx)", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę z danymi (ISBN lub Tytuł):", df_in.columns)
    
    if st.button("Rozpocznij proces"):
        if API_KEY == "AIzaSy...":
            st.error("Błąd: Nie podmieniłeś klucza API w kodzie!")
        else:
            final_data = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, row in df_in.iterrows():
                book_query = str(row[target_col])
                status_text.text(f"Przetwarzam ({i+1}/{len(df_in)}): {book_query}")
                
                res = fetch_book_data_gemini(book_query)
                
                entry = {"Szukana fraza": book_query}
                
                # Definiujemy nagłówki tabeli
                headers = [
                    "Tytuł", "Autorzy", "Liczba stron", "Wydawcy", 
                    "Data publikacji", "ISBN-13", "ISBN-10", "Opis", 
                    "Tematy", "Miejsca wydania"
                ]
                
                for h in headers:
                    if res:
                        entry[h] = res.get(h, "Brak")
                    else:
                        entry[h] = "Błąd"
                
                final_data.append(entry)
                
                # Aktualizacja paska postępu
                progress_bar.progress((i + 1) / len(df_in))
                
                # Mała przerwa dla darmowego API (limit zapytań na minutę)
                time.sleep(2) 

            st.session_state.res_df = pd.DataFrame(final_data)
            status_text.success("Katalogowanie zakończone pomyślnie!")

# --- WYŚWIETLANIE WYNIKÓW ---
if 'res_df' in st.session_state:
    df_res = st.session_state.res_df
    
    st.divider()
    
    # Przycisk pobierania
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        df_res.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Pobierz gotowy Excel",
        data=buf.getvalue(),
        file_name="skatalogowane_ksiazki.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    # Podgląd tabeli
    st.dataframe(df_res)
