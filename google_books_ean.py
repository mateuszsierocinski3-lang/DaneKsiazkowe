import streamlit as st
import pandas as pd
import requests
import time
import re
import io
import xml.etree.ElementTree as ET

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Bibliotekarz", page_icon="📖", layout="wide")

# --- NAMESPACE ONIX ---
NS = {'onix': 'http://ns.editeur.org/onix/3.1/reference'}

# --- MAPOWANIE JĘZYKÓW ---
LANG_MAP = {
    'pol': 'polski', 'eng': 'angielski', 'ger': 'niemiecki',
    'fre': 'francuski', 'rus': 'rosyjski', 'ita': 'włoski', 'spa': 'hiszpański'
}

def reverse_authors(authors_str):
    if not authors_str or authors_str in ["Nieznany", "Brak", "Błąd danych"]:
        return authors_str
    individual_authors = [a.strip() for a in authors_str.split(',')]
    reversed_list = []
    for author in individual_authors:
        parts = author.split()
        if len(parts) >= 2:
            last_name = parts[-1]
            first_names = " ".join(parts[:-1])
            reversed_list.append(f"{last_name} {first_names}")
        else:
            reversed_list.append(author)
    return ", ".join(reversed_list)

@st.cache_data(ttl=3600)
def get_elibri_xml(url, username, password):
    try:
        r = requests.get(url, auth=(username, password), timeout=15)
        if r.status_code == 200:
            return r.content
        return None
    except:
        return None

def parse_onix_data(xml_content):
    try:
        root = ET.fromstring(xml_content)
        # Próbujemy znaleźć Product niezależnie od poziomu zagłębienia
        product = root.find('.//onix:Product', NS)
        if product is None: return None

        def get_text_anywhere(tag_name):
            # Szuka tagu wewnątrz całego produktu, ignorując strukturę
            node = product.find(f'.//onix:{tag_name}', NS)
            return node.text.strip() if node is not None and node.text else "Brak"

        # 1. ISBN
        isbn13 = "Brak"
        for ident in product.findall('.//onix:ProductIdentifier', NS):
            type_id = ident.find('onix:ProductIDType', NS)
            if type_id is not None and type_id.text == "15":
                val = ident.find('onix:IDValue', NS)
                if val is not None: isbn13 = val.text

        # 2. Tytuł
        title = get_text_anywhere('TitleText')

        # 3. Autorzy
        authors = []
        for contrib in product.findall('.//onix:Contributor', NS):
            p_name = contrib.find('onix:PersonName', NS)
            if p_name is not None: authors.append(p_name.text)
        authors_str = ", ".join(authors) if authors else "Nieznany"

        # 4. Seria
        series = get_text_anywhere('TitleText') # To może wymagać doprecyzowania jeśli są kolizje
        # Lepiej:
        coll = product.find('.//onix:Collection', NS)
        series_str = coll.find('.//onix:TitleText', NS).text if coll is not None and coll.find('.//onix:TitleText', NS) is not None else "Brak serii"

        # 5. Język
        lang_node = product.find('.//onix:LanguageCode', NS)
        lang_code = lang_node.text.lower() if lang_node is not None else "pol"
        language = LANG_MAP.get(lang_code, lang_code)

        # 6. OPIS WYDANIA (Najbardziej odporna logika)
        ed_stat = get_text_anywhere('EditionStatement')
        ed_num = get_text_anywhere('EditionNumber')
        
        if ed_stat != "Brak":
            edition_final = "Pierwsze" if ed_stat == "1" else ed_stat
        elif ed_num != "Brak":
            edition_final = "Pierwsze" if ed_num == "1" else f"Wydanie {ed_num}"
        else:
            edition_final = "Brak informacji"

        # 7. Data Premiery
        pub_date_raw = get_text_anywhere('Date')
        if len(pub_date_raw) == 8:
            pub_date = f"{pub_date_raw[:4]}-{pub_date_raw[4:6]}-{pub_date_raw[6:]}"
        else:
            pub_date = pub_date_raw

        # 8. Okładka
        cover_url = "Brak linku"
        for res in product.findall('.//onix:SupportingResource', NS):
            if res.find('.//onix:ResourceContentType[text()="01"]', NS) is not None:
                link = res.find('.//onix:ResourceLink', NS)
                if link is not None: cover_url = link.text.strip()

        # 9. Pozostałe
        publisher = get_text_anywhere('PublisherName')
        pages = get_text_anywhere('ExtentValue')
        
        # Opis (TextContent)
        desc = "Brak opisu"
        text_node = product.find('.//onix:TextContent[onix:TextType="03"]/onix:Text', NS)
        if text_node is not None and text_node.text:
            desc = re.sub('<[^<]+?>', '', text_node.text).strip()

        return {
            "Tytuł": title, "Autorzy": authors_str, "Język": language, "Seria": series_str,
            "Opis wydania": edition_final, "Data premiery": pub_date, "Wydawca": publisher,
            "Liczba stron": pages, "ISBN-13": isbn13, "Opis": desc[:500] + "...", "Link do okładki": cover_url
        }
    except:
        return None

# --- UI ---
st.title("📖 Bibliotekarz")
with st.sidebar:
    elibri_user = st.text_input("User", value="empik")
    elibri_pass = st.text_input("Pass", type="password", value="sjdhg235!S")

uploaded_file = st.file_uploader("Excel", type=["xlsx"])

if uploaded_file:
    df_in = pd.read_excel(uploaded_file)
    target_col = st.selectbox("Kolumna ISBN:", df_in.columns)
    
    if st.button("Pobierz"):
        final_data = []
        progress = st.progress(0)
        
        for i, row in df_in.iterrows():
            # CZYSZCZENIE ISBN
            raw_isbn = str(row[target_col]).split('.')[0].strip()
            isbn = re.sub(r'\D', '', raw_isbn) # zostaw tylko cyfry
            
            xml = get_elibri_xml(f"https://www.elibri.com.pl/distributors/empik/by_isbn/{isbn}", elibri_user, elibri_pass)
            info = parse_onix_data(xml) if xml else None
            
            entry = {"Identyfikator": isbn}
            headers = ["Tytuł", "Autorzy", "Język", "Seria", "Opis wydania", "Data premiery", "Wydawca", "Liczba stron", "ISBN-13", "Opis", "Link do okładki"]
            
            for h in headers:
                entry[h] = info.get(h, "Brak danych") if info else "Nie znaleziono w eLibri"
            
            entry["Autorzy (odwróceni)"] = reverse_authors(entry["Autorzy"])
            final_data.append(entry)
            progress.progress((i + 1) / len(df_in))

        res_df = pd.DataFrame(final_data)
        # Przesunięcie kolumny autorów
        cols = list(res_df.columns)
        if "Autorzy" in cols and "Autorzy (odwróceni)" in cols:
            idx = cols.index("Autorzy")
            cols.insert(idx + 1, cols.pop(cols.index("Autorzy (odwróceni)")))
            res_df = res_df[cols]
            
        st.session_state.results_df = res_df
        st.dataframe(res_df)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            res_df.to_excel(writer, index=False)
        st.download_button("Pobierz Excel", buf.getvalue(), "rejestr.xlsx")
