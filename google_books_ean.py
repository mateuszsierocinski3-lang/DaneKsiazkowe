import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import xml.etree.ElementTree as ET

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz Pro", page_icon="📖", layout="wide")

# --- FUNKCJE POMOCNICZE ---

def reverse_authors(authors_str):
    """Zamienia 'Imię Nazwisko' na 'Nazwisko Imię' dla każdego autora na liście."""
    if not authors_str or authors_str in ["Nieznany", "Brak", "Błąd danych"]:
        return authors_str
    
    parts = authors_str.split(",")  # Rozdzielamy autorów
    reversed_parts = []
    
    for part in parts:
        name_atoms = part.strip().split()
        if len(name_atoms) >= 2:
            # Zakładamy, że ostatni człon to nazwisko, reszta to imiona
            last_name = name_atoms[-1]
            first_names = " ".join(name_atoms[:-1])
            reversed_parts.append(f"{last_name} {first_names}")
        else:
            # Jeśli jest tylko jeden człon (np. pseudonim), zostawiamy jak jest
            reversed_parts.append(part.strip())
            
    return ", ".join(reversed_parts)

def find_text(parent, path):
    """Bezpieczne pobieranie tekstu z węzła XML."""
    node = parent.find(path)
    return node.text.strip() if node is not None and node.text else None

# --- PARSER ONIX ---
def parse_onix_data(xml_content):
    try:
        # Dekodowanie i czyszczenie XML z przestrzeni nazw (Namespace), co ułatwia dostęp przez find()
        xml_content_str = xml_content.decode('utf-8') if isinstance(xml_content, bytes) else xml_content
        xml_content_str = re.sub(r'\sxmlns="[^"]+"', '', xml_content_str, count=1)
        
        root = ET.fromstring(xml_content_str)
        product = root if root.tag == 'Product' else root.find('.//Product')
        if product is None: return None

        # 1. Identyfikatory
        isbn13 = "Brak"
        for ident in product.findall('.//ProductIdentifier'):
            if find_text(ident, 'ProductIDType') == "15":
                isbn13 = find_text(ident, 'IDValue')

        # 2. Tytuł (TitleDetail -> TitleElement -> TitleText)
        title = find_text(product, './/TitleDetail[TitleType="01"]//TitleText') or "Brak tytułu"

        # 3. Autorzy (Oryginalni)
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

        # 5. Opis wydania i strony
        desc_detail = product.find('DescriptiveDetail')
        edition_display = "Brak"
        pages = "Brak"
        if desc_detail is not None:
            ed_stat = find_text(desc_detail, 'EditionStatement')
            if ed_stat:
                edition_display = "Pierwsze" if ed_stat == "1" else ed_stat
            
            pages = find_text(desc_detail, './/Extent[ExtentType="00"]/ExtentValue')

        # 6. Opis (z CDATA i HTML)
        description = "Brak opisu"
        text_content = product.find('.//TextContent[TextType="03"]/Text')
        if text_content is not None:
            raw_html = text_content.text or ""
            description = re.sub('<[^<]+?>', '', raw_html).strip()

        # 7. Okładka
        cover_url = "Brak okładki"
        res_link = product.find('.//SupportingResource[ResourceContentType="01"]//ResourceLink')
        if res_link is not None: 
            cover_url = res_link.text

        # 8. Wydawca i Cena
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
            "Seria": series_str,
            "Opis wydania": edition_display,
            "Wydawca": publisher,
            "Imprint": imprint,
            "Liczba stron": pages,
            "ISBN-13": isbn13,
            "Cena": price_str,
            "Opis": description[:500] + "..." if len(description) > 500 else description,
            "Link do okładki": cover_url
        }
    except Exception:
        return None

# --- UI STREAMLIT ---
with st.sidebar:
    st.header("🔑 Autoryzacja eLibri")
    elibri_user = st.text_input("Username (API)", value="empik")
    elibri_pass = st.text_input("Password (API)", type="password", value="sjdhg235!S")
    st.info("Skrypt automatycznie odwraca kolejność imion i nazwisk w dodatkowej kolumnie.")

st.title("📖 Bibliotekarz ONIX (eLibri)")

uploaded_file = st.file_uploader("Załaduj plik Excel z kolumną ISBN", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Wybierz kolumnę z numerami ISBN:", df_in.columns)
    
    if st.button("Pobierz dane z API"):
        final_data = []
        progress_bar = st.progress(0)
        
        # Nagłówki w docelowej kolejności
        headers = [
            "Tytuł", "Autorzy", "Autorzy (Nazwisko Imię)", "Seria", 
            "Opis wydania", "Wydawca", "Imprint", "Liczba stron", 
            "ISBN-13", "Cena", "Opis", "Link do okładki"
        ]
        
        for i, row in df_in.iterrows():
            # Czyszczenie ISBN (usuwanie .0 jeśli Excel zamienił na float)
            isbn_raw = str(row[target_col]).split('.')[0].strip()
            
            # Zapytanie API
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
                    entry[h] = "Nie znaleziono / Błąd"
            
            final_data.append(entry)
            progress_bar.progress((i + 1) / len(df_in))
            time.sleep(0.05) # Mały delay dla stabilności

        st.session_state.results_df = pd.DataFrame(final_data)
        st.success("Dane zostały pobrane!")

if 'results_df' in st.session_state:
    st.subheader("Podgląd danych")
    st.dataframe(st.session_state.results_df)
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        st.session_state.results_df.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Pobierz gotowy plik Excel",
        data=buf.getvalue(),
        file_name="rejestr_ksiazek_elibri.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
