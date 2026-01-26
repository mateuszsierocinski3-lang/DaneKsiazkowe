import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import time

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz AI - Naprawiony", page_icon="📖")

# --- KLUCZ API (Wstaw swój klucz z AI Studio poniżej) ---
API_KEY = "AIzaSy..." 

# Konfiguracja bezpiecznego połączenia
if API_KEY != "AIzaSyAng8dcG9iUIQ6L2H5iK7QuHkiPSovJ3eU":
    try:
        genai.configure(api_key=API_KEY)
        # Używamy konkretnej, pełnej ścieżki do modelu, co często rozwiązuje błąd 404
        model = genai.GenerativeModel('models/gemini-1.5-flash')
    except Exception as e:
        st.error(f"Błąd konfiguracji: {e}")
else:
    st.warning("Wklej swój klucz API w linii 12 kodu!")

def fetch_book_data(query):
    try:
        # Bardzo uproszczony prompt - mniejsza szansa na błąd modelu
        prompt = f"Podaj dane książki: {query}. Odpowiedz tylko czystym JSON: {{\"Tytuł\":\"\", \"Autorzy\":\"\", \"Opis\":\"\"}}"
        
        # Próba generowania z obsługą błędów wersji
        response = model.generate_content(prompt)
        
        # Wyciąganie tekstu i czyszczenie z ewentualnych znaczników ```json
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        
        return json.loads(raw_text)
    except Exception as e:
        # To pokaże nam, czy błąd 404 nadal występuje, czy jest to inny problem
        st.error(f"Błąd dla {query}: {str(e)}")
        return None

# --- INTERFEJS ---
st.title("📚 Bibliotekarz Gemini")
st.info("Jeśli nadal widzisz błąd 404, upewnij się, że klucz pochodzi z Google AI Studio, a nie z Google Cloud Console.")

uploaded_file = st.file_uploader("Załaduj plik Excel", type=["xlsx"])

if uploaded_file and API_KEY != "AIzaSy...":
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę z ISBN/Tytułem:", df_in.columns)
    
    if st.button("Uruchom katalogowanie"):
        final_results = []
        progress_bar = st.progress(0)
        
        for i, row in df_in.iterrows():
            q = str(row[target_col])
            res = fetch_book_data(q)
            
            entry = {"Szukana fraza": q}
            # Mapowanie pól z JSONa do Excela
            entry["Tytuł"] = res.get("Tytuł", "Brak") if res else "Błąd"
            entry["Autorzy"] = res.get("Autorzy", "Brak") if res else "Błąd"
            entry["Opis"] = res.get("Opis", "Brak") if res else "Błąd"
            
            final_results.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            # Czekamy 2 sekundy (limit 15 zapytań na minutę w wersji darmowej)
            time.sleep(2)
            
        st.session_state.final_df = pd.DataFrame(final_results)
        st.success("Katalogowanie zakończone!")

# --- WYNIKI ---
if 'final_df' in st.session_state:
    st.dataframe(st.session_state.final_df)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        st.session_state.final_df.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Pobierz wynikowy Excel",
        data=output.getvalue(),
        file_name="wyniki_ai.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
