import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Układ szeroki
st.set_page_config(page_title="Terminal / Kiosk KM", layout="wide")

# Zaawansowana stylizacja CSS (kafelki biletomatu)
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

# Bezpieczna aktualizacja tabeli dla opłat
try:
    c.execute("ALTER TABLE historia_kontroli ADD COLUMN status_oplaty TEXT DEFAULT 'Nieopłacony'")
    conn.commit()
except sqlite3.OperationalError:
    pass

# Automatyczne dodanie kont domyślnych (w tym kiosku, jeśli go brakuje)
domyslne_konta = [
    ("konduktor", "123", "Kontroler", "Jan Konduktor (ID: 104)"),
    ("admin", "admin123", "Administrator", "Kierownik Pociągu"),
    ("kiosk", "123", "Kiosk", "Automat Biletowy Stacjonarny (Kiosk-01)")
]
for l, h, r, i in domyslne_konta:
    c.execute("INSERT OR IGNORE INTO uzytkownicy (login, haslo, rola, imie) VALUES (?, ?, ?, ?)", (l, h, r, i))
conn.commit()

# ================= TRWAŁY STAN SESJI =================
if "zalogowany" not in st.session_state:
    st.session_state["zalogowany"] = False
if "user" not in st.session_state:
    st.session_state["user"] = ""
if "rola" not in st.session_state:
    st.session_state["rola"] = ""

# Stany dla kiosku (wybór biletu i krok płatności)
if "kiosk_krok" not in st.session_state:
    st.session_state["kiosk_krok"] = "wybor"
if "kiosk_wybrany_bilet" not in st.session_state:
    st.session_state["kiosk_wybrany_bilet"] = None
if "kiosk_cena" not in st.session_state:
    st.session_state["kiosk_cena"] = 0.0

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
            <p style="color: #94a3b8; margin:5px 0 0 0; font-size: 13px;">Wybierz terminal / Logowanie</p>
        </div>
    """, unsafe_allow_html=True)

    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    with col_l2:
        with st.form("form_log"):
            st.write("### Autoryzacja urządzenia")
            l_in = st.text_input("Login / ID urządzenia (np. konduktor, kiosk):")
            h_in = st.text_input("Kod PIN / Hasło:", type="password")
            
            btn_zaloguj = st.form_submit_button("Uruchom terminal")
            if btn_zaloguj:
                c.execute("SELECT rola, imie FROM uzytkownicy WHERE login = ? AND haslo = ?", (l_in.strip(), h_in))
                res = c.fetchone()
                if res:
                    st.session_state["zalogowany"] = True
                    st.session_state["rola"] = res[0]
                    st.session_state["user"] = res[1]
                    st.session_state["kiosk_krok"] = "wybor" # reset kroków kiosku przy logowaniu
                    st.rerun()
                else:
                    st.error("Błędny login lub PIN.")
    st.stop()


# ================= SPECJALNY TRYB: KIOSK (2 RZĘDY PO 3 KAFELKI) =================
if st.session_state["rola"] == "Kiosk":
    st.markdown("""
        <div style="text-align: center; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 15px; border-radius: 10px; border-bottom: 4px solid #f97316; margin-bottom: 20px;">
            <h1 style="color: #f97316; margin:0;">🚊 AUTOMAT BILETOWY KOLEI MAZOWIECKICH</h1>
            <p style="color: #94a3b8; margin: 5px 0 0 0;">Dotknij wybranego biletu, aby przejść do płatności.</p>
        </div>
    """, unsafe_allow_html=True)

    # Definicja 6 biletów (2 rzędy po 3 pozycje)
    katalog_biletow = [
        {"nazwa": "Bilet jednorazowy normalny", "cena": 15.50, "opis": "Ważny 3 h od skasowania"},
        {"nazwa": "Bilet jednorazowy ulgowy (50%)", "cena": 7.75, "opis": "Wymagany dokument uprawniający"},
        {"nazwa": "Bilet sieciowy dobowy", "cena": 45.00, "opis": "Nieograniczone przejazdy przez 24h"},
        {"nazwa": "Bilet weekendowy KM", "cena": 39.00, "opis": "Od piątku od 19:00 do poniedziałku do 06:00"},
        {"nazwa": "Bilet strefowy miejski", "cena": 6.80, "opis": "Warszawa i strefa miejska"},
        {"nazwa": "Bilet aglomeracyjny", "cena": 12.00, "opis": "Warszawa + otaczające gminy"}
    ]

    # KROK 1: WYBÓR BILETU (2 RZĘDY PO 3 KOLUMNY)
    if st.session_state["kiosk_krok"] == "wybor":
        st.write("### Krok 1 z 2: Wybierz rodzaj biletu")
        
        # Podział na 2 rzędy po 3 kolumny
        rząd_1 = katalog_biletow[0:3]
        rząd_2 = katalog_biletow[3:6]

        def wybierz_bilet(nazwa, cena):
            st.session_state["kiosk_wybrany_bilet"] = nazwa
            st.session_state["kiosk_cena"] = cena
            st.session_state["kiosk_krok"] = "platnosc"

        # Pierwszy rząd
        cols1 = st.columns(3)
        for idx, bilet in enumerate(rząd_1):
            with cols1[idx]:
                st.markdown(f"""
                    <div style="background-color: #1e293b; border: 2px solid #334155; padding: 18px; border-radius: 10px; text-align: center; min-height: 140px; margin-bottom: 10px;">
                        <h4 style="color: #f8fafc; margin-top:0; font-size: 16px;">{bilet['nazwa']}</h4>
                        <p style="color: #94a3b8; font-size: 12px; margin-bottom: 10px;">{bilet['opis']}</p>
                        <h2 style="color: #f97316; margin: 0; font-size: 24px;">{bilet['cena']:.2f} zł</h2>
                    </div>
                """, unsafe_allow_html=True)
                if st.button(f"Wybierz: {bilet['nazwa'].split()[0]}...", key=f"btn_b_{idx}"):
                    wybierz_bilet(bilet['nazwa'], bilet['cena'])
                    st.rerun()

        # Drugi rząd
        cols2 = st.columns(3)
        for idx, bilet in enumerate(rząd_2):
            with cols2[idx]:
                st.markdown(f"""
                    <div style="background-color: #1e293b; border: 2px solid #334155; padding: 18px; border-radius: 10px; text-align: center; min-height: 140px; margin-bottom: 10px;">
                        <h4 style="color: #f8fafc; margin-top:0; font-size: 16px;">{bilet['nazwa']}</h4>
                        <p style="color: #94a3b8; font-size: 12px; margin-bottom: 10px;">{bilet['opis']}</p>
                        <h2 style="color: #f97316; margin: 0; font-size: 24px;">{bilet['cena']:.2f} zł</h2>
                    </div>
                """, unsafe_allow_html=True)
                if st.button(f"Wybierz: {bilet['nazwa'].split()[0]}...", key=f"btn_b_{idx+3}"):
                    wybierz_bilet(bilet['nazwa'], bilet['cena'])
                    st.rerun()

    # KROK 2: PŁATNOŚĆ I WYDANIE BILETU
    elif st.session_state["kiosk_krok"] == "platnosc":
        st.write("### Krok 2 z 2: Płatność i wydanie biletu")
        
        c_podsumowanie, c_form_pl = st.columns(2)
        
        with c_podsumowanie:
            st.markdown(f"""
                <div class="mandat-box" style="border-color: #f97316;">
                    <h3 style="color: #f97316; margin-top:0;">Podsumowanie zakupu</h3>
                    <p><b>Wybrany bilet:</b> {st.session_state['kiosk_wybrany_bilet']}</p>
                    <h2 style="color: #22c55e; margin: 15px 0;">Do zapłaty: {st.session_state['kiosk_cena']:.2f} PLN</h2>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("⬅ Wróć do wyboru biletów"):
                st.session_state["kiosk_krok"] = "wybor"
                st.rerun()

        with c_form_pl:
            with st.form("form_platnosc_kiosk"):
                relacja_kiosk = st.text_input("Stacja docelowa / Relacja:", value="Warszawa Centralna -> Pruszków")
                metoda_pl = st.radio("Wybierz metodę płatności:", [
                    "💳 Karta płatnicza (Zbliżeniowa)",
                    "📱 BLIK",
                    "💵 Gotówka (Banknoty/Monety)"
                ])
                
                btn_finalizuj = st.form_submit_button("🖨️ ZAPŁAĆ I DRUKUJ BILET", type="primary")

                if btn_finalizuj:
                    kod_auto = f"KM-AUTO-{datetime.now().strftime('%H%M%S')}"
                    waznosc_auto = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
                    
                    c.execute("INSERT INTO bilety (kod_biletu, rodzaj, data_waznosci, status) VALUES (?, ?, ?, ?)",
                              (kod_auto, f"{st.session_state['kiosk_wybrany_bilet']} | {relacja_kiosk}", waznosc_auto, "Aktywny"))
                    conn.commit()

                    st.success("Transakcja zatwierdzona! Bilet został wydany.")
                    st.markdown(f"""
                        <div class="mandat-box" style="border-color: #22c55e;">
                            <h3 style="color: #22c55e; margin-top:0; text-align:center;">BILET KOLEJOWY - WERSJA CYFROWA</h3>
                            <h4 style="text-align:center; color: #f97316; margin-bottom: 10px;">KOD: {kod_auto}</h4>
                            <p><b>Oferta:</b> {st.session_state['kiosk_wybrany_bilet']}</p>
                            <p><b>Relacja:</b> {relacja_kiosk}</p>
                            <p><b>Ważny do:</b> {waznosc_auto}</p>
                            <p><b>Zapłacono:</b> {st.session_state['kiosk_cena']:.2f} PLN ({metoda_pl})</p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Przycisk resetu do ekranu głównego kiosku
                    if st.button("Kup kolejny bilet"):
                        st.session_state["kiosk_krok"] = "wybor"
                        st.rerun()

    st.markdown("---")
    # Panel serwisowy kiosku (zabezpieczony PIN-em)
    with st.expander("🛠️ Panel serwisowy / Wyjdź z trybu kiosku (Wymaga PIN)"):
        pin_wyjscie = st.text_input("Podaj kod PIN serwisowy:", type="password")
        if st.button("Wyloguj kiosk"):
            if pin_wyjscie == "123" or pin_wyjscie == "admin123":
                st.session_state["zalogowany"] = False
                st.session_state["user"] = ""
                st.session_state["rola"] = ""
                st.rerun()
            else:
                st.error("Błędny PIN serwisowy!")

    st.stop() # Blokuje resztę kodu dla roli Kiosk


# ================= MENU BOCZNE DLA KONDUKTORA / ADMINA =================
with st.sidebar:
    st.markdown("""
        <div style="text-align: center; padding: 10px 0 20px 0;">
            <h3 style="color: #f97316; margin:0;">Koleje Mazowieckie</h3>
            <p style="color: #64748b; font-size: 11px; margin:0;">Terminal Konduktorski</p>
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
    if st.button("🚪 Wyloguj urządzenie"):
        st.session_state["zalogowany"] = False
        st.session_state["user"] = ""
        st.session_state["rola"] = ""
        st.rerun()

# ================= GŁÓWNY OBSZAR ROBOCZY (KONDUKTOR / ADMIN) =================
st.markdown(f"""
    <div class="terminal-header">
        <h2 style="margin:0; color: #f97316;">Terminal Przenośny - System Konduktorski</h2>
        <p style="margin:2px 0 0 0; color: #94a3b8; font-size:13px;">Zalogowany: <b>{st.session_state['user']}</b> | Status: <b>Online</b></p>
    </div>
""", unsafe_allow_html=True)

# 1. BILETY
if wybrane_menu == "🎫 Bilety":
    pod_menu = st.selectbox("Wybierz operację biletową:", [
        "🔍 Kontrola (Skaner kodów)", 
        "➕ Nowy bilet (Sprzedaż u konduktora)", 
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
            st.markdown(f'<div class="card-metric" style="border-left: 4px solid #f97316;"><h3>{st.session_state["p_kary"]} zł</h3><p>Suma kar</p></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.write("### Skanowanie kodu biletowego")
        
        def wyczysc_pole_skanera():
            st.session_state["skaner_input"] = ""

        col_skan_1, col_skan_2 = st.columns([4, 1])
        with col_skan_1:
            kod_wejscie = st.text_input("Zeskanuj kod kreskowy / QR:", key="skaner_input", placeholder="np. KM-AUTO-...")
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
                    st.error(f"❌ **BRAK WAŻNEGO BILETU!**\nKod **{kod_czysty}** nie widnieje w systemie. Nałożono mandat: **{stawka_kary} zł**.")
                    c.execute("INSERT INTO historia_kontroli (kod_biletu, wynik, komentarz, data_kontroli, kontroler, linia, kara, status_oplaty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                              (kod_czysty, "Brak w bazie (Gapowicz)", "Brak dokumentu", str(teraz), st.session_state["user"], pociag_info, stawka_kary, "Nieopłacony"))
                    conn.commit()
                else:
                    b_id, rodzaj, data_wazn_str, status_b = bilet
                    data_waznosci = datetime.strptime(data_wazn_str, "%Y-%m-%d %H:%M")

                    if status_b == "Skasowany":
                        st.session_state["p_gapowiczow"] += 1
                        st.session_state["p_kary"] += stawka_kary
                        st.warning(f"⚠️ **BILET JUŻ WYKORZYSTANY!**\nRodzaj: {rodzaj}. Mandat: **{stawka_kary} zł**.")
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

    elif pod_menu == "➕ Nowy bilet (Sprzedaż u konduktora)":
        with st.form("form_sprzedaz"):
            st.write("### Wystawienie biletu w pociągu")
            trasa = st.text_input("Relacja:")
            rodzaj_biletu = st.selectbox("Oferta:", ["Bilet jednorazowy normalny", "Bilet jednorazowy ulgowy (50%)", "Bilet taryfowy strefowy"])
            cena_biletu = st.number_input("Należność w zł:", value=15.50, step=0.50)
            
            if st.form_submit_button("Wydrukuj bilet"):
                if trasa.strip():
                    kod_nowy = f"KM-SPRZ-{datetime.now().strftime('%H%M%S')}"
                    dw_nowa = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
                    c.execute("INSERT INTO bilety (kod_biletu, rodzaj, data_waznosci, status) VALUES (?, ?, ?, ?)", (kod_nowy, rodzaj_biletu, dw_nowa, "Aktywny"))
                    conn.commit()
                    st.success(f"Wystawiono bilet! Kod: **{kod_nowy}**, Kwota: **{cena_biletu} zł**")
                else:
                    st.error("Podaj relację podróży.")

    elif pod_menu == "⚠ Nowe wezwanie (Mandat za brak biletu)":
        st.write("### 🚨 Wystawianie wezwania do zapłaty")
        with st.form("form_mandat_oficjalny"):
            pasażer_imie = st.text_input("Imię i Nazwisko pasażera:")
            pasażer_dok = st.text_input("Dokument tożsamości / PESEL:")
            pasażer_adres = st.text_input("Adres zamieszkania:")
            pociag_m = st.selectbox("Pociąg / Relacja:", ["KM 12105 (Warszawa W-wa -> Radom)", "KM 21230 (Warszawa Włochy -> Siedlce)"])
            powod_wystawienia = st.selectbox("Powód:", ["Brak ważnego biletu na przejazd", "Brak dokumentu uprawniającego do ulgi"])
            kwota_m = st.number_input("Kwota opłaty dodatkowej (zł):", value=250.0, step=10.0)
            
            if st.form_submit_button("🚨 Wystaw wezwanie", type="primary"):
                if pasażer_imie.strip() and pasażer_dok.strip():
                    teraz = datetime.now()
                    nr_wezwania = f"KM-WEZ-{teraz.strftime('%Y%m%d-%H%M')}"
                    komentarz_pelny = f"Pasażer: {pasażer_imie} | Dok: {pasażer_dok} | Powód: {powod_wystawienia}"
                    c.execute("INSERT INTO historia_kontroli (kod_biletu, wynik, komentarz, data_kontroli, kontroler, linia, kara, status_oplaty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                              (nr_wezwania, "Wezwanie do zapłaty", komentarz_pelny, str(teraz), st.session_state["user"], pociag_m, kwota_m, "Nieopłacony"))
                    conn.commit()
                    st.success(f"Wystawiono wezwanie **{nr_wezwania}** na kwotę **{kwota_m} zł**.")
                else:
                    st.error("Wypełnij imię, nazwisko oraz numer dokumentu.")

    elif pod_menu == "💳 Opłać mandat / Kara":
        st.write("### Terminal płatniczy - Opłacanie kar")
        df_nieopl = pd.read_sql("SELECT id, data_kontroli as [Data], linia as [Pociąg], kod_biletu as [Nr Wezwania], komentarz as [Szczegóły], kara as [Kwota (zł)] FROM historia_kontroli WHERE kara > 0 AND status_oplaty = 'Nieopłacony' ORDER BY id DESC", conn)
        if not df_nieopl.empty:
            st.dataframe(df_nieopl, use_container_width=True, hide_index=True)
            with st.form("form_oplaty"):
                wybrane_id = st.selectbox("Wybierz ID pozycji do opłacenia:", df_nieopl["id"].tolist())
                metoda_platnosci = st.radio("Forma płatności:", ["💳 Karta", "💵 Gotówka", "📱 BLIK"])
                if st.form_submit_button("Zatwierdź płatność"):
                    c.execute("UPDATE historia_kontroli SET status_oplaty = 'Opłacony' WHERE id = ?", (wybrane_id,))
                    conn.commit()
                    st.success("Płatność zatwierdzona!")
                    st.rerun()
        else:
            st.info("Brak nieopłaconych mandatów.")

# Pozostałe zakładki dla konduktora / admina
elif wybrane_menu == "📋 Zadania":
    st.subheader("Zadania i harmonogram")
    st.info("• Zmiana: 06:00 - 14:00\n• Obieg: KM-121")

elif wybrane_menu == "ℹ️ Informacje":
    st.subheader("Komunikaty")
    st.write("Aktualny cennik opłat dodatkowych obowiązkowy w pociągach KM.")

elif wybrane_menu == "📊 Raporty":
    st.subheader("Raport z kontroli")
    df_rap = pd.read_sql("SELECT data_kontroli as [Data], linia as [Pociąg], kontroler as [Konduktor], kod_biletu as [Kod/Wezwanie], wynik as [Wynik], kara as [Kara (zł)], status_oplaty as [Status] FROM historia_kontroli ORDER BY id DESC", conn)
    if not df_rap.empty:
        st.dataframe(df_rap, use_container_width=True, hide_index=True)
        st.metric("Suma kar", f"{df_rap['Kara (zł)'].sum()} zł")

elif wybrane_menu == "🔧 Narzędzia":
    st.subheader("Narzędzia serwisu")
    if st.button("🔄 Synchronizuj bazę"):
        st.success("Zsynchronizowano.")

elif wybrane_menu == "👥 Użytkownicy" and st.session_state["rola"] == "Administrator":
    st.subheader("Zarządzanie kontami")
    df_users = pd.read_sql("SELECT id as [ID], login as [Login], rola as [Rola], imie as [Opis] FROM uzytkownicy", conn)
    st.dataframe(df_users, use_container_width=True, hide_index=True)

elif wybrane_menu == "🎟️ Baza Biletów (Admin)" and st.session_state["rola"] == "Administrator":
    st.subheader("Zarządzanie biletami")
    df_bilety_db = pd.read_sql("SELECT id as [ID], kod_biletu as [Kod], rodzaj as [Oferta], data_waznosci as [Ważny do], status as [Status] FROM bilety ORDER BY id DESC", conn)
    st.dataframe(df_bilety_db, use_container_width=True, hide_index=True)
