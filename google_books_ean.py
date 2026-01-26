import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import time

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz Gemini PRO", page_icon="📚")

# --- KLUCZ API ---
API_KEY = "AIzaSyAng8dcG9iUIQ6L2H5iK7QuHkiPSovJ3eU" # <--- WKLEJ TUTAJ SWÓJ KLUCZ

if API_KEY != "AIzaSy...":
    genai.configure(api_key=API_KEY)
else:
    st.error("Uzupełnij klucz API w kodzie!")

# --- FUNKCJA POBIERANIA DANYCH Z AUTOMATYCZNYM WYBOREM MODELU ---
def fetch_book_data_gemini(query):
    # Lista nazw modeli od najnowszych do najstarszych
    model_names = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "models/gemini-1.5-flash",
        "gemini-pro"
    ]
    
    last_error = ""
    
    for m_name in model_names:
        try:
            model = genai.GenerativeModel(m_name)
            prompt = f"Podaj dane książki: {query}. Zwróć WYŁĄCZNIE JSON: {{'Tytuł':'','Autorzy':'','Opis':'opis po polsku'}}"
            
            # Próba generowania
            response = model.generate_content(prompt)
            
            if response and response.text:
                # Wyciągamy czysty tekst JSON (na wypadek gdyby model dodał ```json)
                clean_text = response.text.replace('```json', '').replace('```', '').strip()
                return json.loads(clean_text)
        except Exception as e:
            last_error = str(e)
            continue # Próbuj kolejny model z listy
            
    st.error(f"❌ Żaden model nie odpowiedział. Ostatni błąd: {last_error}")
    return None

# --- UI ---
st.title("📚 Bibliotekarz AI (Naprawiony)")

uploaded_file = st.file_uploader("Załaduj Excel", type=["xlsx"])

if uploaded_file and API_KEY != "AIzaSy...":
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Kolumna z danymi:", df_in.columns)
    
    if st.button("Uruchom"):
        results = []
        bar = st.progress(0)
        
        for i, row in df_in.iterrows():
            q = str(row[target_col])
            res = fetch_book_data_gemini(q)
            
            row_data = {"Szukana fraza": q}
            fields = ["Tytuł", "Autorzy", "Opis"]
            for f in fields:
                row_data[f] = res.get(f, "Brak") if res else "Błąd"
            
            results.append(row_data)
            bar.progress((i + 1) / len(df_in))
            time.sleep(1.5) # Przerwa dla darmowego konta
            
        st.session_state.final_df = pd.DataFrame(results)
        st.success("Zrobione!")

if 'final_df' in st.session_state:
    st.dataframe(st.session_state.final_df)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.final_df.to_excel(writer, index=False)
    st.download_button("Pobierz wynik", buf.getvalue(), "wynik.xlsx")
