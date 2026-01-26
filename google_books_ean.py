import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import time

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz Gemini AI", page_icon="📚", layout="centered")

# --- KLUCZ API (Wklej swój klucz poniżej) ---
API_KEY = "AIzaSyAng8dcG9iUIQ6L2H5iK7QuHkiPSovJ3eU" 

# Konfiguracja Google AI
if API_KEY != "AIzaSy...":
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.warning("⚠️ Nie zapomnij wkleić swojego klucza API w kodzie (linia 12)!")

# --- FUNKCJA POBIERANIA DANYCH ---
def fetch_book_data_gemini(query):
    if API_KEY == "AIzaSy...":
        return None
        
    try:
        # Prompt wymuszający format JSON
        prompt = f"""
        Znajdź dane książki: "{query}".
        Zwróć dane WYŁĄCZNIE jako obiekt JSON w formacie:
        {{
            "Tytuł": "...",
            "Autorzy": "...",
            "Liczba stron": "...",
            "Wydawcy": "...",
            "Data publikacji": "...",
            "ISBN-13": "...",
            "ISBN-10": "...",
            "Opis": "tutaj stwórz bogaty opis po polsku",
            "Tematy": "...",
            "Miejsca wydania": "..."
        }}
        """
        
        # Ustawienie generowania JSON (wymaga nowszej biblioteki)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
        )
        
        if response and response.text:
            return json.loads(response.text)
        return None

    except Exception as e:
        # To wyświetli nam konkretny powód błędu w aplikacji
        st.error(f"❌ Błąd dla '{query}': {str(e)}")
        return None

# --- UI APLIKACJI ---
st.title("📚 Bibliotekarz Gemini (Darmowy)")
st.write("Skonfigurowano model: **Gemini 1.5 Flash**")

uploaded_file = st.file_uploader("Załaduj plik Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę z ISBN/Tytułem:", df_in.columns)
    
    if st.button("Rozpocznij katalogowanie"):
        final_data = []
        progress_bar = st.progress(0)
        status_msg = st.empty()
        
        for i, row in df_in.iterrows():
            book_query = str(row[target_col])
            status_msg.info(f"Przetwarzam {i+1}/{len(df_in)}: {book_query}")
            
            # Wywołanie AI
            res = fetch_book_data_gemini(book_query)
            
            entry = {"Szukana fraza": book_query}
            headers = [
                "Tytuł", "Autorzy", "Liczba stron", "Wydawcy", 
                "Data publikacji", "ISBN-13", "ISBN-10", "Opis", 
                "Tematy", "Miejsca wydania"
            ]
            
            for h in headers:
                if res:
                    entry[h] = res.get(h, "Brak danych")
                else:
                    entry[h] = "BŁĄD (zobacz komunikat wyżej)"
            
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            
            # Czekamy 2 sekundy, żeby nie przekroczyć darmowego limitu (15 RPM)
            time.sleep(2)

        st.session_state.results_df = pd.DataFrame(final_data)
        status_msg.success("Zakończono! Możesz pobrać plik.")

# --- WYŚWIETLANIE I POBIERANIE ---
if 'results_df' in st.session_state:
    df_res = st.session_state.results_df
    
    # Przygotowanie Excela w pamięci
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        df_res.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Pobierz gotowy raport Excel",
        data=buf.getvalue(),
        file_name="skatalogowane_ksiazki_gemini.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.dataframe(df_res)
