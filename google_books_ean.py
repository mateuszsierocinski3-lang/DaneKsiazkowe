import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import time

st.set_page_config(page_title="Bibliotekarz AI - Naprawa", page_icon="📚")

# --- KLUCZ API ---
API_KEY = "AIzaSyAng8dcG9iUIQ6L2H5iK7QuHkiPSovJ3eU" 

def fetch_book_data(query):
    # Próbujemy najpierw 1.5-flash, a jak nie ma, to starszy gemini-pro
    for model_name in ['gemini-1.5-flash', 'gemini-pro']:
        try:
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel(model_name)
            
            prompt = f"Podaj dane książki o kodzie/tytule: {query}. Odpowiedz TYLKO JSON: {{\"Tytuł\":\"\", \"Autorzy\":\"\", \"Opis\":\"\"}}"
            response = model.generate_content(prompt)
            
            text = response.text.strip()
            if "```" in text:
                text = text.split("```")[1].replace("json", "").strip()
            
            return json.loads(text)
        except Exception as e:
            # Jeśli to błąd 404, próbujemy następny model z listy
            if "404" in str(e):
                continue
            st.error(f"Błąd krytyczny: {e}")
            return None
    return None

st.title("📚 Bibliotekarz AI (Wersja Multi-Model)")

uploaded_file = st.file_uploader("Załaduj plik Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę:", df_in.columns)
    
    if st.button("URUCHOM"):
        if "AIza" not in API_KEY:
            st.error("Wklej klucz API w kodzie!")
        else:
            final_results = []
            bar = st.progress(0)
            
            for i, row in df_in.iterrows():
                q = str(row[target_col])
                res = fetch_book_data(q)
                
                entry = {"Szukana fraza": q}
                entry["Tytuł"] = res.get("Tytuł", "Brak") if res else "Błąd"
                entry["Autorzy"] = res.get("Autorzy", "Brak") if res else "Błąd"
                entry["Opis"] = res.get("Opis", "Brak") if res else "Błąd"
                
                final_results.append(entry)
                bar.progress((i + 1) / len(df_in))
                time.sleep(1)
            
            st.session_state.df = pd.DataFrame(final_results)
            st.success("Zakończono!")

if 'df' in st.session_state:
    st.dataframe(st.session_state.df)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.df.to_excel(writer, index=False)
    st.download_button("Pobierz wynik", buf.getvalue(), "wynik.xlsx")
