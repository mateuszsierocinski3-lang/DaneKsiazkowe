import streamlit as st
import pandas as pd
import openai
import json
import io
import random
import time

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz AI", page_icon="🤖", layout="centered")

# --- STYLE I ANIMACJA ---
st.markdown("""
<style>
    .book-container { display: flex; justify-content: center; padding: 20px; }
    .loader-book { width: 50px; height: 35px; position: relative; border: 3px solid #2c3e50; background: white; }
    .loader-book::after { content: ''; position: absolute; left: 50%; top: 0; width: 1px; height: 100%; background: #2c3e50; }
    .page { position: absolute; right: 0; top: 0; width: 50%; height: 100%; background: #f0f0f0; transform-origin: left center; animation: flip 1.2s infinite ease-in-out; border-left: 1px solid #ccc; }
    @keyframes flip { 0% { transform: rotateY(0deg); } 80%, 100% { transform: rotateY(-180deg); } }
    .quote-style { text-align: center; font-family: 'Georgia', serif; font-style: italic; color: #2c3e50; background: #fdfcf0; padding: 20px; border-left: 5px solid #2c3e50; margin: 20px 0; }
</style>
""", unsafe_allow_html=True)

CYTATY_MONTE_CHRISTO = [
    "„Cała mądrość ludzka zawiera się w tych dwóch słowach: Czekać i pokładać nadzieję!”",
    "„Wszyscy jesteśmy sprawcami własnego losu.”",
    "„Tylko ten, kto poznał smak najwyższej rozpaczy, zdolny jest odczuć największe szczęście.”"
]

# --- LOGIKA AI ---
def fetch_book_data_ai(api_key, book_info_input):
    client = openai.OpenAI(api_key=api_key)
    
    prompt = f"""
    Jesteś profesjonalnym bibliotekarzem. Na podstawie poniższych danych: "{book_info_input}", 
    znajdź informacje o książce i zwróć je w formacie JSON. 
    W polu 'Opis' wygeneruj wyczerpujący, atrakcyjny opis książki (minimum 3-4 zdania).
    
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
    Jeśli nie znasz jakiejś danej, wpisz "Brak danych". Odpowiadaj tylko czystym JSONem.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Szybki i tani model
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Błąd API: {e}")
        return None

# --- UI ---
st.title("🤖 Bibliotekarz AI")
st.subheader("Inteligentne Katalogowanie z GPT")

# Pole na klucz API
api_key = "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", type="password")

if 'results_df' not in st.session_state:
    st.session_state.results_df = None

uploaded_file = st.file_uploader("Załaduj plik Excel (z kolumną ISBN lub Tytułami)", type=["xlsx"])

if uploaded_file and api_key:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę z danymi wejściowymi (ISBN lub Tytuł):", df_in.columns)
    
    if st.button("Uruchom silnik AI"):
        final_data = []
        progress_bar = st.progress(0)
        status_msg = st.empty()
        
        anim_placeholder = st.empty()
        anim_placeholder.markdown('<div class="book-container"><div class="loader-book"><div class="page"></div></div></div>', unsafe_allow_html=True)
        
        quote_placeholder = st.empty()
        quote_placeholder.markdown(f'<div class="quote-style">{random.choice(CYTATY_MONTE_CHRISTO)}<br><small>— Aleksander Dumas</small></div>', unsafe_allow_html=True)

        for i, row in df_in.iterrows():
            book_query = row[target_col]
            status_msg.markdown(f"Analiza AI dla: `{book_query}`")
            
            # Pobieranie danych z GPT
            book_info = fetch_book_data_ai(api_key, book_query)
            
            entry = {"Identyfikator wejściowy": book_query}
            
            headers = [
                "Tytuł", "Autorzy", "Liczba stron", "Wydawcy", "Data publikacji", 
                "ISBN-13", "ISBN-10", "Opis", "Tematy", "Miejsca wydania"
            ]
            
            for h in headers:
                if book_info:
                    entry[h] = book_info.get(h, "Brak")
                else:
                    entry[h] = "Błąd przetwarzania"
            
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            
        anim_placeholder.empty()
        quote_placeholder.empty()
        status_msg.success("Zasoby zostały skatalogowane przez AI.")
        st.session_state.results_df = pd.DataFrame(final_data)

elif uploaded_file and not api_key:
    st.warning("👈 Proszę wprowadzić klucz API w pasku bocznym.")

# --- WYŚWIETLANIE I POBIERANIE ---
if st.session_state.results_df is not None:
    df_res = st.session_state.results_df
    
    # Przygotowanie pliku do pobrania
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        df_res.to_excel(writer, index=False)
    
    st.download_button("📥 Pobierz Rejestr AI (Excel)", buf.getvalue(), "rejestr_ai.xlsx")
    st.dataframe(df_res)
