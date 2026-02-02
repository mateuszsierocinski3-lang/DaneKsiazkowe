import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import xml.etree.ElementTree as ET

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz Pro", page_icon="📖", layout="wide")

# --- SŁOWNIK JĘZYKÓW ---
LANG_MAP = {
    "pol": "polski",
    "eng": "angielski",
    "ger": "niemiecki",
    "fre": "francuski",
    "rus": "rosyjski",
    "ita": "włoski",
    "spa": "hiszpański",
    "lat": "łacina",
    "cze": "czeski",
    "ukr": "ukraiński"
}

# --- FUNKCJE POMOCNICZE ---

def reverse_authors(authors_str):
    """Zamienia 'Imię Nazwisko' na 'Nazwisko Imię' dla każdego autora na liście."""
    if not authors_str or authors_str in ["Nieznany", "Brak", "Błąd danych"]:
        return authors_str
    
    parts = authors_str.split(",") 
    reversed_parts = []
    
    for part in parts:
        name_atoms = part.strip().split()
        if len(name_atoms) >= 2:
            last_name = name_atoms[-1]
            first_names = " ".join(name_atoms[:-1])
            reversed_parts.append(f"{last_name} {first_names}")
        else:
            reversed_parts.append(part.strip())
            
    return ", ".join(reversed_parts)

def find_text(parent, path):
    """Bezpieczne pobieranie tekstu z węzła XML."""
    node = parent.find(path)
    return node.text.strip() if node is not None and node.text else None

def format_date(date_str):
    """Formatuje datę z YYYYMMDD na YYYY-MM-DD."""
    if date_str and len(date_str) >= 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str

# --- PARSER ONIX ---
def parse_onix_data(xml_content):
    try:
        xml_content_str = xml_content.decode('utf-8') if isinstance(xml_content, bytes) else xml_content
        xml_content_str = re.sub(r'\sxmlns="[^"]+"', '', xml_content_str, count=1)
        
        root = ET.fromstring(xml_content_str)
        product = root if root.tag == 'Product' else root.find('.//Product')
        if product is None: return None

        # 1. Identyfikatory
        isbn13 = find_text(product, './/ProductIdentifier[ProductIDType="15"]/IDValue') or "Brak"

        # 2. Tytuł
        title = find_text(product, './/TitleDetail[TitleType="01"]//TitleText') or "Brak tytułu"

        # 3. Autorzy
        authors = []
        for contrib in product.findall('.//Contributor'):
            name = find_text(contrib, 'PersonName')
            if name: authors.append(name)
        authors_str = ", ".join(authors) if authors else "Nieznany"

        # 4. Seria Wydawnicza
        series_names = []
        for series in product.findall('.//Collection'):
            s_title = find_text(series, './/TitleText')
            if s_title: series_names.append(s_title)
        series_str = ", ".join(series_names) if series_names else "Brak serii"

        # 5. Opis wydania, strony i JĘZYK
        desc_detail = product.find('DescriptiveDetail')
        edition_display = "Brak"
        pages = "Brak"
        language_display = "Brak"
        
        if desc_detail is not None:
            ed_stat = find_text(desc_detail, 'EditionStatement')
            if ed_stat:
                edition_display = "Pierwsze" if ed_stat == "1" else ed_stat
            pages = find_text(desc_detail, './/Extent[ExtentType="00"]/ExtentValue')
            
            # Pobieranie języka (LanguageRole 01 = język tekstu)
            lang_node = desc_detail.find('.//Language[LanguageRole="01"]/LanguageCode')
            if lang_node is not None:
                l_code = lang_node.text.strip().lower()
                language_display = LANG_MAP.get(l_code, l_code.upper())

        # 6. Data Premiery
        pub_date_raw = find_text(product, './/PublishingDate[PublishingDateRole="01"]/Date')
        release_date = format_date(pub_date_raw) or "Brak daty"

        # 7. Opis (USUNIĘTO OGRANICZENIE ZNAKÓW)
        description = "Brak opisu"
        text_content = product.find('.//TextContent[TextType="03"]/Text')
        if text_content is not None:
            raw_html = text_content.text or ""
            # Usuwanie tagów HTML dla czystego tekstu
            description = re.sub('<[^<]+?>', '', raw_html).strip()

        # 8. Okładka
        cover_url = "Brak okładki"
        res_link = product.find('.//SupportingResource[ResourceContentType="01"]//ResourceLink')
        if res_link is not None: 
            cover_url = res_link.text

        # 9. Wydawca i Cena
        publisher = find_text(product, './/Publisher/PublisherName') or "Brak"
        imprint = find_text(product, './/Imprint/ImprintName') or "Brak"
        
        price_node = product.find('.//Price[PriceType="02"]')
        price_str = "Brak"
        if price_node is not None:
            amt = find_text(price_node, 'PriceAmount')
            cur = find_text(price_node, 'CurrencyCode')
            price_str = f"{amt} {cur}"

        return {
            "Tytuł": title,
            "Autorzy": authors_str,
            "Autorzy (Nazwisko Imię)": reverse_authors(authors_str),
            "Język": language_display,
            "Data premiery": release_date,
            "Seria": series_str,
            "Opis wydania": edition_display,
            "Wydawca": publisher,
            "Imprint": imprint,
            "Liczba stron": pages,
            "ISBN-13": isbn13,
            "Cena": price_str,
            "Opis": description,  # Pobiera całość bez skracania
            "Link do okładki": cover_url
        }
    except Exception:
        return None

# --- UI STREAMLIT ---
with st.sidebar:
    st.header("🔑 Autoryzacja eLibri")
    elibri_user = st.text_input("Username (API)", value="empik")
    elibri_pass = st.text_input("Password (API)", type="password", value="sjdhg235!S")

st.title("📖 Bibliotekarz ONIX (eLibri)")

uploaded_file = st.file_uploader("Załaduj plik Excel z kolumną ISBN", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę z numerami ISBN:", df_in.columns)
    
    if st.button("Pobierz dane z API"):
        final_data = []
        progress_bar = st.progress(0)
        
        headers = [
            "Tytuł", "Autorzy", "Autorzy (Nazwisko Imię)", "Język", "Data premiery", "Seria", 
            "Opis wydania", "Wydawca", "Imprint", "Liczba stron", 
            "ISBN-13", "Cena", "Opis", "Link do okładki"
        ]
        
        for i, row in df_in.iterrows():
            isbn_raw = str(row[target_col]).split('.')[0].strip()
            
            url = f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn_raw}"
            try:
                r = requests.get(url, auth=(elibri_user, elibri_pass), timeout=10)
                xml_res = r.content if r.status_code == 200 else None
            except:
                xml_res = None
            
            book_info = parse_onix_data(xml_res) if xml_res else None
            
            entry = {"Identyfikator": isbn_raw}
            if book_info:
                for h in headers:
                    entry[h] = book_info.get(h, "Brak")
            else:
                for h in headers:
                    entry[h] = "Błąd / Nie znaleziono"
            
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            time.sleep(0.05)

        st.session_state.results_df = pd.DataFrame(final_data)
        st.success("Dane zostały pobrane!")

if 'results_df' in st.session_state:
    # W podglądzie Streamlit opisy mogą wyglądać na ucięte, 
    # ale w pliku Excel będzie cała treść.
    st.dataframe(st.session_state.results_df)
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    st.download_button("📥 Pobierz Excel", buf.getvalue(), "rejestr_elibri.xlsx")
