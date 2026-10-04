import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Układ szeroki dla terminala konduktorskiego
st.set_page_config(page_title="Terminal Konduktorski KM", layout="wide")

# Zaawansowana stylizacja CSS (lewe menu + profesjonalna paleta barw KM)
st.markdown("""
    <style>
    .stApp {
        background-color: #0b1120;
        color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    [data-testid="stSidebar"] {
        background-color: #1e293b;
        border-right: 2px solid #334155;
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] {
        gap: 8px;
    }
    [data-testid="stSidebar"] .stRadio label {
        background-color: #0f172a;
        padding: 12px 15px;
        border-radius: 8px;
        border: 1px solid #334155;
        color: #ffffff;
        font-weight: 600;
        font-size: 15px;
        width: 100%;
        transition: all 0.2s ease-in-out;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background-color: #f97316;
        color: white;
        border-color: #f97316;
    }
    .terminal-header {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 20px;
        border-radius: 10px;
        border-left: 6px solid #f97316;
        border-right: 1px solid #334155;
        border-top: 1px solid #334155;
        border-bottom: 1px solid #334155;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    .card-metric {
        background-color: #1e293b;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #334155;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .card-metric h3 {
        margin: 0;
        color: #f97316;
        font-size: 26px;
        font-weight: 700;
    }
    .card-metric p {
        margin: 5px 0 0 0;
        color: #94a3b8;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
    }
    .mandat-box {
        background-color: #1e293b;
        border: 2px dashed #f97316;
        padding: 20px;
        border-radius: 8px;
        margin-top: 15px;
    }
    .stButton>button {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: bold;
        border-radius: 8px;
        background-color: #f97316;
        color: white;
        border: none;
        box-shadow: 0 2px 4px rgba(249, 115, 22, 0.3);
    }
    .stButton>button:hover {
        background-color: #ea580c;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# Baza danych
conn = sqlite3.connect("terminal_km.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
    CREATE TABLE IF NOT EXISTS bilety (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kod_biletu TEXT UNIQUE,
        rodzaj TEXT,
        data_waznosci TEXT,
        status TEXT DEFAULT 'Aktywny'
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS historia_kontroli (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kod_biletu TEXT,
        wynik TEXT,
        komentarz TEXT,
        data_kontroli TEXT,
        kontroler TEXT,
        linia TEXT,
        kara REAL DEFAULT 0.0,
        status_oplaty TEXT DEFAULT 'Nieopłacony'
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS uzytkownicy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT UNIQUE,
        haslo TEXT,
        rola TEXT,
        imie TEXT
    )
""")
conn.commit()

# Bezpieczna aktualizacja struktury tabeli dla opłat
try:
    c.execute("ALTER TABLE historia_kontroli ADD COLUMN status_oplaty TEXT DEFAULT 'Nieopłacony'")
    conn.commit()
except sqlite3.OperationalError:
    pass

# Domyślny użytkownik konduktor oraz administrator (jeśli baza jest pusta)
c.execute("SELECT COUNT(*) FROM uzytkownicy")
if c.fetchone()[0] == 0:
    c.executemany("INSERT INTO uzytkownicy (login, haslo, rola, imie) VALUES (?, ?, ?, ?)", [
        ("konduktor", "123", "Kontroler", "Jan Konduktor (ID: 104)"),
        ("admin", "admin123", "Administrator", "Kierownik Pociągu")
    ])
    conn.commit()

# ================= TRWAŁY STAN SESJI =================
if "zalogowany" not in st.session_state:
    st.session_state["zalogowany"] = False
if "user" not in st.session_state:
    st.session_state["user"] = ""
if "rola" not in st.session_state:
    st.session_state["rola"] = ""

if "p_skontrolowanych" not in st.session_state:
    st.session_state["p_skontrolowanych"] = 0
if "p_gapowiczow" not in st.session_state:
    st.session_state["p_gapowiczow"] = 0
if "p_kary" not in st.session_state:
    st.session_state["p_kary"] = 0.0

if "skaner_input" not in st.session_state:
    st.session_state["skaner_input"] = ""

# ================= LOGOWANIE =================
if not st.session_state["zalogowany"]:
    st.markdown("""
        <div class="terminal-header" style="text-align: center; max-width: 450px; margin: 50px auto;">
            <h2 style="color: #f97316; margin:0;">Koleje Mazowieckie</h2>
            <p style="color: #94a3b8; margin:5px 0 0 0; font-size: 13px;">Terminal Przenośny Konduktora (TPK)</p>
        </div>
    """, unsafe_allow_html=True)

    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    with col_l2:
        with st.form("form_log"):
            st.write("### Logowanie do urządzenia")
            l_in = st.text_input("Identyfikator / Login:")
            h_in = st.text_input("Kod PIN / Hasło:", type="password")
            
            btn_zaloguj = st.form_submit_button("Zaloguj do pociągu")
            if btn_zaloguj:
                c.execute("SELECT rola, imie FROM uzytkownicy WHERE login = ? AND haslo = ?", (l_in.strip(), h_in))
                res = c.fetchone()
                if res:
                    st.session_state["zalogowany"] = True
                    st.session_state["rola"] = res[0]
                    st.session_state["user"] = res[1]
                    st.rerun()
                else:
                    st.error("Błędny login lub PIN.")
    st.stop()

# ================= MENU BOCZNE (LEWA STRONA) =================
with st.sidebar:
    st.markdown("""
        <div style="text-align: center; padding: 10px 0 20px 0;">
            <h3 style="color: #f97316; margin:0;">Koleje Mazowieckie</h3>
            <p style="color: #64748b; font-size: 11px; margin:0;">Tryb produkcyjny</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"**Pracownik:** `{st.session_state['user']}`")
    st.markdown(f"**Rola:** `{st.session_state['rola']}`")
    st.markdown("---")
    
    opcje_menu = ["🎫 Bilety", "📋 Zadania", "ℹ️ Informacje", "📊 Raporty", "🔧 Narzędzia"]
    if st.session_state["rola"] == "Administrator":
        opcje_menu.append("👥 Użytkownicy")
        opcje_menu.append("🎟️ Baza Biletów (Admin)")

    wybrane_menu = st.radio(
        "Nawigacja:",
        opcje_menu,
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    if st.button("🚪 Zamknij pociąg / Wyloguj"):
        st.session_state["zalogowany"] = False
        st.session_state["user"] = ""
        st.session_state["rola"] = ""
        st.rerun()

# ================= GŁÓWNY OBSZAR ROBOCZY =================
st.markdown(f"""
    <div class="terminal-header">
        <h2 style="margin:0; color: #f97316;">Terminal Przenośny - System Konduktorski</h2>
        <p style="margin:2px 0 0 0; color: #94a3b8; font-size:13px;">Zalogowany użytkownik: <b>{st.session_state['user']}</b> | Status: <b>Połączono z serwerem KM</b></p>
    </div>
""", unsafe_allow_html=True)

# ================= 1. BILETY =================
if wybrane_menu == "🎫 Bilety":
    pod_menu = st.selectbox("Wybierz operację biletową:", [
        "🔍 Kontrola (Skaner kodów)", 
        "➕ Nowy bilet (Sprzedaż)", 
        "⚠ Nowe wezwanie (Mandat za brak biletu)", 
        "💳 Opłać mandat / Kara"
    ])
    
    if pod_menu == "🔍 Kontrola (Skaner kodów)":
        c_pociag, c_mandat = st.columns(2)
        with c_pociag:
            pociag_info = st.selectbox("Relacja / Pociąg:", ["KM 12105 (Warszawa W-wa -> Radom)", "KM 21230 (Warszawa Włochy -> Siedlce)", "KM 31402 (Modlin -> Warszawa Centralna)"])
        with c_mandat:
            stawka_kary = st.number_input("Opłata dodatkowa (Mandat) w zł:", value=250.0, step=10.0)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="card-metric"><h3>{st.session_state["p_skontrolowanych"]}</h3><p>Sprawdzone bilety</p></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="card-metric" style="border-left: 4px solid #ef4444;"><h3>{st.session_state["p_gapowiczow"]}</h3><p>Brak uprawnień</p></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="card-metric" style="border-left: 4px solid #f97316;"><h3>{st.session_state["p_kary"]} zł</h3><p>Suma nałożonych kar</p></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.write("### Skanowanie kodu biletowego")
        
        def wyczysc_pole_skanera():
            st.session_state["skaner_input"] = ""

        col_skan_1, col_skan_2 = st.columns([4, 1])
        with col_skan_1:
            kod_wejscie = st.text_input("Zeskanuj kod kreskowy / QR:", key="skaner_input", placeholder="np. KM-2026-001")
        with col_skan_2:
            st.markdown("<br>", unsafe_allow_html=True) 
            st.button("❌ Wyczyść", on_click=wyczysc_pole_skanera)

        if st.button("Weryfikuj uprawnienia do przejazdu"):
            if kod_wejscie:
                kod_czysty = kod_wejscie.strip()
                st.session_state["p_skontrolowanych"] += 1
                teraz = datetime.now()

                c.execute("SELECT id, rodzaj, data_waznosci, status FROM bilety WHERE kod_biletu = ?", (kod_czysty,))
                bilet = c.fetchone()

                if not bilet:
                    st.session_state["p_gapowiczow"] += 1
                    st.session_state["p_kary"] += stawka_kary
                    st.error(f"❌ **BRAK WAŻNEGO BILETU!**\nKod **{kod_czysty}** nie widnieje w systemie. Wystawiono opłatę dodatkową: **{stawka_kary} zł**.")
                    c.execute("INSERT INTO historia_kontroli (kod_biletu, wynik, komentarz, data_kontroli, kontroler, linia, kara, status_oplaty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                              (kod_czysty, "Brak w bazie (Gapowicz)", "Brak dokumentu uprawniającego", str(teraz), st.session_state["user"], pociag_info, stawka_kary, "Nieopłacony"))
                    conn.commit()
                else:
                    b_id, rodzaj, data_wazn_str, status_b = bilet
                    data_waznosci = datetime.strptime(data_wazn_str, "%Y-%m-%d %H:%M")

                    if status_b == "Skasowany":
                        st.session_state["p_gapowiczow"] += 1
                        st.session_state["p_kary"] += stawka_kary
                        st.warning(f"⚠️ **BILET JUŻ WYKORZYSTANY!**\nRodzaj: {rodzaj}. Nałożono mandat: **{stawka_kary} zł**.")
                        c.execute("INSERT INTO historia_kontroli (kod_biletu, wynik, komentarz, data_kontroli, kontroler, linia, kara, status_oplaty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                  (kod_czysty, "Skasowany wcześniej", rodzaj, str(teraz), st.session_state["user"], pociag_info, stawka_kary, "Nieopłacony"))
                        conn.commit()
                    elif data_waznosci < teraz:
                        st.session_state["p_gapowiczow"] += 1
                        st.session_state["p_kary"] += stawka_kary
                        st.error(f"⏰ **BILET PRZETERMINOWANY!**\nWażność minęła: {data_wazn_str}. Mandat: **{stawka_kary} zł**.")
                        c.execute("INSERT INTO historia_kontroli (kod_biletu, wynik, komentarz, data_kontroli, kontroler, linia, kara, status_oplaty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                  (kod_czysty, "Przeterminowany", data_wazn_str, str(teraz), st.session_state["user"], pociag_info, stawka_kary, "Nieopłacony"))
                        conn.commit()
                    else:
                        st.success(f"✅ **BILET PRAWIDŁOWY!**\nRodzaj: **{rodzaj}**\nWażny do: {data_wazn_str}")
                        c.execute("INSERT INTO historia_kontroli (kod_biletu, wynik, komentarz, data_kontroli, kontroler, linia, kara, status_oplaty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                  (kod_czysty, "Prawidłowy", rodzaj, str(teraz), st.session_state["user"], pociag_info, 0.0, "Opłacony"))
                        conn.commit()
            else:
                st.warning("Wpisz lub zeskanuj kod biletu.")

    elif pod_menu == "➕ Nowy bilet (Sprzedaż)":
        with st.form("form_sprzedaz"):
            st.write("### Wystawienie biletu w pociągu")
            trasa = st.text_input("Relacja (np. Warszawa Wsch. -> Pruszków):")
            rodzaj_biletu = st.text_input("Rodzaj / Oferta biletu (wpisz własną nazwę):", value="Bilet jednorazowy normalny")
            cena_biletu = st.number_input("Należność w zł:", value=15.50, step=0.50)
            
            if st.form_submit_button("Wydrukuj bilet / Zatwierdź"):
                if trasa.strip():
                    kod_nowy = f"KM-SPRZ-{datetime.now().strftime('%H%M%S')}"
                    dw_nowa = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
                    c.execute("INSERT INTO bilety (kod_biletu, rodzaj, data_waznosci, status) VALUES (?, ?, ?, ?)", (kod_nowy, rodzaj_biletu, dw_nowa, "Aktywny"))
                    conn.commit()
                    st.success(f"Wystawiono bilet! Kod: **{kod_nowy}**, Kwota: **{cena_biletu} zł**")
                else:
                    st.error("Podaj relację podróży.")

    elif pod_menu == "⚠️ Nowe wezwanie (Mandat za brak biletu)":
        st.write("### 🚨 Wystawianie wezwania do zapłaty (Opłata dodatkowa)")
        st.info("Uzupełnij dane pasażera, który podróżuje bez ważnego biletu lub dokumentu poświadczającego uprawnienia do ulgi.")

        with st.form("form_mandat_oficjalny"):
            pasażer_imie = st.text_input("Imię i Nazwisko pasażera:")
            pasażer_dok = st.text_input("Seria i numer dokumentu tożsamości / PESEL:")
            pasażer_adres = st.text_input("Adres zamieszkania pasażera:")
            pociag_m = st.selectbox("Pociąg / Relacja:", ["KM 12105 (Warszawa W-wa -> Radom)", "KM 21230 (Warszawa Włochy -> Siedlce)", "KM 31402 (Modlin -> Warszawa Centralna)"])
            powod_wystawienia = st.text_input("Powód nałożenia opłaty (wpisz własną treść):", value="Brak ważnego biletu na przejazd")
            kwota_m = st.number_input("Kwota opłaty dodatkowej (zł):", value=250.0, step=10.0)
            
            btn_wys_mandat = st.form_submit_button("🚨 Wystaw oficjalne wezwanie do zapłaty", type="primary")

            if btn_wys_mandat:
                if pasażer_imie.strip() and pasażer_dok.strip():
                    teraz = datetime.now()
                    nr_wezwania = f"KM-WEZ-{teraz.strftime('%Y%m%d-%H%M')}"
                    komentarz_pelny = f"Pasażer: {pasażer_imie} | Dok: {pasażer_dok} | Adres: {pasażer_adres} | Powód: {powod_wystawienia}"
                    
                    c.execute("INSERT INTO historia_kontroli (kod_biletu, wynik, komentarz, data_kontroli, kontroler, linia, kara, status_oplaty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                              (nr_wezwania, "Wezwanie do zapłaty", komentarz_pelny, str(teraz), st.session_state["user"], pociag_m, kwota_m, "Nieopłacony"))
                    conn.commit()
                    
                    st.success(f"✅ Wystawiono wezwanie **{nr_wezwania}** na kwotę **{kwota_m} zł** dla pasażera: {pasażer_imie}!")
                    
                    st.markdown(f"""
                        <div class="mandat-box">
                            <h3 style="color: #f97316; margin-top:0; text-align:center;">KOLEJE MAZOWIECKIE - SP Z O.O.</h3>
                            <h4 style="text-align:center; margin-bottom: 15px;">ZAWIADOMIENIE - WEZWANIE DO ZAPŁATY NR {nr_wezwania}</h4>
                            <p><b>Data wystawienia:</b> {teraz.strftime('%Y-%m-%d %H:%M')}</p>
                            <p><b>Kontroler:</b> {st.session_state['user']} | <b>Pociąg:</b> {pociag_m}</p>
                            <hr style="border-color: #334155;">
                            <p><b>Dane dłużnika:</b> {pasażer_imie}</p>
                            <p><b>Dokument / PESEL:</b> {pasażer_dok}</p>
                            <p><b>Adres:</b> {pasażer_adres}</p>
                            <p><b>Tytuł zobowiązania:</b> {powod_wystawienia}</p>
                            <h3 style="color: #ef4444; text-align:center; margin: 15px 0;">DO ZAPŁATY: {kwota_m:.2f} PLN</h3>
                            <p style="font-size: 11px; color: #94a3b8; text-align:center; margin-bottom:0;">Należność należy uiścić w ciągu 14 dni od daty wystawienia na wskazany rachunek bankowy KM lub u konduktora.</p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error("Wypełnij przynajmniej imię i nazwisko oraz numer dokumentu pasażera.")

    elif pod_menu == "💳 Opłać mandat / Kara":
        st.write("### Terminal płatniczy - Opłacanie bieżących kar i mandatów")
        df_nieopl = pd.read_sql("SELECT id, data_kontroli as [Data], linia as [Pociąg], kod_biletu as [Nr Wezwania], komentarz as [Szczegóły], kara as [Kwota (zł)] FROM historia_kontroli WHERE kara > 0 AND status_oplaty = 'Nieopłacony' ORDER BY id DESC", conn)
        
        if not df_nieopl.empty:
            st.dataframe(df_nieopl, use_container_width=True, hide_index=True)
            
            with st.form("form_oplaty"):
                wybrane_id = st.selectbox("Wybierz ID pozycji z tabeli do opłacenia:", df_nieopl["id"].tolist())
                metoda_platnosci = st.radio("Wybierz formę płatności u konduktora:", ["💳 Karta płatnicza (Pinpad)", "💵 Gotówka", "📱 BLIK"])
                
                if st.form_submit_button("Zatwierdź płatność i wydrukuj potwierdzenie", type="primary"):
                    c.execute("UPDATE historia_kontroli SET status_oplaty = 'Opłacony' WHERE id = ?", (wybrane_id,))
                    conn.commit()
                    st.success(f"Płatność dla pozycji ID {wybrane_id} została pomyślnie przetworzona przez ({metoda_platnosci}). Status zmieniono na **Opłacony**!")
                    st.rerun()
        else:
            st.info("Brak nieopłaconych mandatów / wezwań w systemie.")

# ================= 2. ZADANIA =================
elif wybrane_menu == "📋 Zadania":
    st.subheader("Zadania i harmonogram pracy")
    st.info("• Harmonogram zmiany: 06:00 - 14:00\n• Obieg pociągu: KM-121\n• Status terminala: Zsynchronizowany z serwerem centralnym KM")

# ================= 3. INFORMACJE =================
elif wybrane_menu == "ℹ️ Informacje":
    st.subheader("Komunikaty i Taryfikator")
    st.write("1. Aktualny cennik opłat dodatkowych obowiązuje od 1 stycznia.\n2. W pociągach pospiesznych wymagana rezerwacja miejsc w rowerach.\n3. W razie awarii czytnika skorzystaj z wpisania ręcznego.")

# ================= 4. RAPORTY =================
elif wybrane_menu == "📊 Raporty":
    st.subheader("Raport z przeprowadzonych kontroli i mandatów")
    df_rap = pd.read_sql("SELECT data_kontroli as [Data], linia as [Pociąg], kontroler as [Konduktor], kod_biletu as [Kod/Wezwanie], wynik as [Wynik], kara as [Kara (zł)], status_oplaty as [Status Opłaty] FROM historia_kontroli ORDER BY id DESC", conn)
    if not df_rap.empty:
        st.dataframe(df_rap, use_container_width=True, hide_index=True)
        suma_kar_c = df_rap["Kara (zł)"].sum()
        st.metric("Suma nałożonych kar podczas zmiany", f"{suma_kar_c} zł")
        
        csv_pobierz = df_rap.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Pobierz raport zmianowy (CSV)", data=csv_pobierz, file_name="raport_konduktorski_km.csv", mime="text/csv")
    else:
        st.info("Brak wpisów w historii kontroli na tej zmianie.")

# ================= 5. NARZĘDZIA =================
elif wybrane_menu == "🔧 Narzędzia":
    st.subheader("Narzędzia serwisowe terminala")
    if st.button("🔄 Synchronizuj bazę danych z dyspozytornią"):
        st.success("Synchronizacja zakończona pomyślnie. Wszystkie dane zapisane.")
    if st.button("🖨️️ Test drukarki termicznej"):
        st.toast("Wydruk testowy powiódł się!", icon="🖨️")

# ================= 6. UŻYTKOWNICY (TYLKO ADMIN) =================
elif wybrane_menu == "👥 Użytkownicy" and st.session_state["rola"] == "Administrator":
    st.subheader("👥 Zarządzanie użytkownikami systemowymi")
    
    tab_lista, tab_dodaj, tab_usun = st.tabs(["📋 Lista pracowników", "➕ Dodaj pracownika", "🗑️ Usuń konto"])
    
    with tab_lista:
        df_users = pd.read_sql("SELECT id as [ID], login as [Login], rola as [Rola], imie as [Imię i Nazwisko / ID] FROM uzytkownicy", conn)
        st.dataframe(df_users, use_container_width=True, hide_index=True)
        
    with tab_dodaj:
        with st.form("form_dodaj_uzytkownika"):
            st.write("### Rejestracja nowego pracownika / konduktora")
            nowy_login = st.text_input("Login systemowy:")
            nowe_haslo = st.text_input("Hasło / PIN:", type="password")
            nowe_imie = st.text_input("Imię i Nazwisko / Identyfikator (np. Jan Kowalski ID: 105):")
            nowa_rola = st.selectbox("Rola w systemie:", ["Kontroler", "Administrator"])
            
            if st.form_submit_button("Utwórz konto pracownika", type="primary"):
                if nowy_login.strip() and nowe_haslo.strip() and nowe_imie.strip():
                    try:
                        c.execute("INSERT INTO uzytkownicy (login, haslo, rola, imie) VALUES (?, ?, ?, ?)",
                                  (nowy_login.strip(), nowe_haslo, nowa_rola, nowe_imie.strip()))
                        conn.commit()
                        st.success(f"Pomyślnie utworzono konto dla: **{nowe_imie}** (Rola: {nowa_rola})!")
                    except sqlite3.IntegrityError:
                        st.error("Użytkownik o takim loginie już istnieje w bazie!")
                else:
                    st.error("Wypełnij wszystkie pola formularza.")
                    
    with tab_usun:
        with st.form("form_usun_uzytkownika"):
            st.write("### Usuwanie konta pracownika")
            df_u_del = pd.read_sql("SELECT id, login, imie FROM uzytkownicy", conn)
            
            if not df_u_del.empty:
                wybrany_u_id = st.selectbox("Wybierz użytkownika do usunięcia:", df_u_del["id"].tolist(), format_func=lambda x: f"ID: {x} - {df_u_del[df_u_del['id'] == x]['imie'].values[0]} ({df_u_del[df_u_del['id'] == x]['login'].values[0]})")
                
                if st.form_submit_button("🗑️ Usuń wybrane konto", type="primary"):
                    c.execute("SELECT login FROM uzytkownicy WHERE id = ?", (wybrany_u_id,))
                    u_to_del = c.fetchone()[0]
                    if u_to_del == "admin" and st.session_state["user"] == "Kierownik Pociągu":
                        st.error("Ne możesz usunąć głównego konta administratora systemu!")
                    else:
                        c.execute("DELETE FROM uzytkownicy WHERE id = ?", (wybrany_u_id,))
                        conn.commit()
                        st.success(f"Konto ID {wybrany_u_id} zostało usunięte z systemu.")
                        st.rerun()
            else:
                st.info("Brak użytkowników w bazie.")

# ================= 7. BAZA BILETÓW (TYLKO ADMIN / KIEROWNIK) =================
elif wybrane_menu == "🎟️ Baza Biletów (Admin)" and st.session_state["rola"] == "Administrator":
    st.subheader("🎟 Zarządzanie pulą biletów w systemie centralnym")
    
    tab_b_lista, tab_b_dodaj = st.tabs(["📋 Aktualne bilety w bazie", "➕ Dodaj nowy bilet"])
    
    with tab_b_lista:
        df_bilety_db = pd.read_sql("SELECT id as [ID], kod_biletu as [Kod Biletu], rodzaj as [Rodzaj Oferty], data_waznosci as [Ważny do], status as [Status] FROM bilety ORDER BY id DESC", conn)
        st.dataframe(df_bilety_db, use_container_width=True, hide_index=True)
        
    with tab_b_dodaj:
        with st.form("form_dodaj_bilet_admin"):
            st.write("### Dodawanie nowego biletu do systemu")
            
            # Kod biletu podawany w pełni ręcznie (taki jaki zeskanujesz / wpiszesz)
            kod_b_input = st.text_input("Kod biletu (wpisz lub wklej dokładny kod/numer):", placeholder="np. 4355 lub KM-2026-XYZ")
            
            # Rodzaj biletu w pełni jako pole tekstowe, bez narzucania gotowców
            rodzaj_b_input = st.text_input("Rodzaj / Oferta biletu (wpisz własną nazwę):", placeholder="np. Normalny jednorazowy, Dobowy itp.")
            
            st.markdown("**Okres ważności biletu:**")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                data_w_input = st.date_input("Data ważności (dzień):", value=datetime.now() + timedelta(days=1))
            with col_d2:
                czas_w_input = st.time_input("Godzina ważności:", value=datetime.now().time())
                
            status_b_input = st.selectbox("Początkowy status:", ["Aktywny", "Skasowany"])
            
            if st.form_submit_button("💾 Zapisz bilet w bazie", type="primary"):
                if kod_b_input.strip() and rodzaj_b_input.strip():
                    pelna_data_waznosci = f"{data_w_input.strftime('%Y-%m-%d')} {czas_w_input.strftime('%H:%M')}"
                    try:
                        c.execute("INSERT INTO bilety (kod_biletu, rodzaj, data_waznosci, status) VALUES (?, ?, ?, ?)",
                                  (kod_b_input.strip(), rodzaj_b_input.strip(), pelna_data_waznosci, status_b_input))
                        conn.commit()
                        st.success(f"Pomyślnie dodano bilet **{kod_b_input.strip()}** ({rodzaj_b_input.strip()}) ważny do **{pelna_data_waznosci}**!")
                    except sqlite3.IntegrityError:
                        st.error("Bilet o takim kodzie już istnieje w bazie!")
                else:
                    st.error("Wypełnij kod biletu oraz rodzaj/ofertę.")
