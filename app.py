import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- SEITEN-KONFIGURATION ---
st.set_page_config(page_title="Performance & Nutrition Dashboard", page_icon="⚡", layout="wide")

st.title("⚡ Performance & Nutrition Dashboard")
st.markdown("Deine Live-Daten von Intervals.icu, kombiniert mit Energy Availability & Makro-Periodisierung.")

# --- SIDEBAR: AUTHENTIFIZIERUNG & USER-DATEN ---
st.sidebar.header("🔑 API & Einstellungen")

# Nutzung von Streamlit Secrets (falls hinterlegt) oder manueller Eingabe
default_athlete_id = st.secrets["INTERVALS_ATHLETE_ID"] if "INTERVALS_ATHLETE_ID" in st.secrets else ""
default_api_key = st.secrets["INTERVALS_API_KEY"] if "INTERVALS_API_KEY" in st.secrets else ""

athlete_id = st.sidebar.text_input("Intervals Athlete ID", value=default_athlete_id, type="default")
api_key = st.sidebar.text_input("Intervals API Key", value=default_api_key, type="password")

st.sidebar.divider()
st.sidebar.header("👤 Biometrische Daten")
weight_kg = st.sidebar.number_input("Körpergewicht (kg)", value=72.0, step=0.5)
body_fat_pct = st.sidebar.slider("Körperfettanteil (%)", min_value=5.0, max_value=30.0, value=12.0, step=0.5)
age = st.sidebar.number_input("Alter", value=30, step=1)
height_cm = st.sidebar.number_input("Größe (cm)", value=180, step=1)
gender = st.sidebar.selectbox("Geschlecht", ["Männlich", "Weiblich"])

# Grundumsatz berechnen (Mifflin-St. Jeor Formel)
if gender == "Männlich":
    bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
else:
    bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

# Magermasse (Fat Free Mass - FFM)
ffm_kg = weight_kg * (1 - (body_fat_pct / 100))

# --- API DATEN ABRUFEN ---
if not athlete_id or not api_key:
    st.warning("⚠️ Bitte gib deine Intervals.icu Athlete ID und deinen API Key in der Sidebar ein (oder hinterlege sie in den Streamlit Secrets).")
else:
    # HTTP Basic Auth für Intervals.icu ('API_KEY' als Username, Key selbst als Passwort)
    auth = ('API_KEY', api_key)
    
    # Zeitraum definieren (letzte 7 Tage bis nächste 3 Tage)
    today = datetime.today().date()
    start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date = (today + timedelta(days=3)).strftime('%Y-%m-%d')
    
    # Daten sauber über gecachte Funktionen abrufen
    @st.cache_data(ttl=600)
    def fetch_intervals_data(a_id, a_key, start, end):
        auth_tuple = ('API_KEY', a_key)
        w_res = requests.get(f"https://intervals.icu/api/v1/athlete/{a_id}/wellness?oldest={start}&newest={end}", auth=auth_tuple)
        e_res = requests.get(f"https://intervals.icu/api/v1/athlete/{a_id}/events?oldest={start}&newest={end}", auth=auth_tuple)
        
        w_data = w_res.json() if w_res.status_code == 200 else []
        e_data = e_res.json() if e_res.status_code == 200 else []
        return w_data, e_data, w_res.status_code, e_res.status_code

    wellness_list, events_list, status_w, status_e = fetch_intervals_data(athlete_id, api_key, start_date, end_date)

    if status_w == 200 and status_e == 200:
        
        # Neuestes Gewicht aus Wellness ziehen falls vorhanden
        latest_weight = weight_kg
        for w in reversed(wellness_list):
            if 'weight' in w and w['weight']:
                latest_weight = w['weight']
                break

        # --- HAUPTBEREICH: METRIKEN ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Aktuelles Gewicht", f"{latest_weight} kg")
        col2.metric("Berechneter BMR", f"{int(bmr)} kcal")
        col3.metric("Magermasse (FFM)", f"{round(ffm_kg, 1)} kg")
        col4.metric("Status API", "Verbunden ✅", delta="Intervals.icu")

        st.divider()

        # --- WORKOUTS & FUELING PLANUNG ---
        st.subheader("📅 Anstehende Workouts & Carb-Empfehlung")
        
        future_events = [e for e in events_list if e.get('start_date_local', '') >= str(today)]
        
        if future_events:
            for ev in future_events:
                ev_name = ev.get('name', 'Training')
                ev_date = ev.get('start_date_local', '').split('T')[0]
                ev_type = ev.get('type', 'Ride')
                moving_time = ev.get('moving_time', 0) / 60  # Minuten
                planned_load = ev.get('icu_training_load', 0) # TSS
                
                # Einfache Logik für Kohlenhydrat-Empfehlung basierend auf TSS / Dauer
                if planned_load > 100 or moving_time > 90:
                    carb_rec = f"{round(weight_kg * 8)}g - {round(weight_kg * 10)}g"
                    fuel_advice = "Hohe Intensität: ~90g+ Kohlenhydrate pro Stunde während des Workouts."
                elif planned_load > 50:
                    carb_rec = f"{round(weight_kg * 6)}g - {round(weight_kg * 8)}g"
                    fuel_advice = "Moderate Einheit: ~60g Kohlenhydrate pro Stunde."
                else:
                    carb_rec = f"{round(weight_kg * 4)}g - {round(weight_kg * 5)}g"
                    fuel_advice = "Erholung / Z2: Wasser / Elektrolyte reichen meist aus."

                with st.expander(f"🚴‍♂️ {ev_date}: {ev_name} ({ev_type} | ca. {int(planned_load)} TSS)"):
                    st.write(f"**Empfohlene Tages-Kohlenhydrate:** {carb_rec}")
                    st.write(f"**Intra-Workout Fueling:** {fuel_advice}")
        else:
            st.info("Keine zukünftigen Events im abgefragten Zeitraum gefunden.")

        # --- ENERGY AVAILABILITY RECHNER ---
        st.divider()
        st.subheader("🔋 Energy Availability (EA) Rechner")
        
        col_ea1, col_ea2 = st.columns(2)
        with col_ea1:
            consumed_cals = st.number_input("Geschätzte Kalorienzufuhr heute (kcal)", value=2800, step=100)
            exercise_cals = st.number_input("Verbrauchte Trainingskalorien (Aktivität) heute (kcal)", value=800, step=50)
        
        with col_ea2:
            # EA Formel: (Intake - Exercise Energy Expenditure) / FFM
            if ffm_kg > 0:
                ea = (consumed_cals - exercise_cals) / ffm_kg
                st.metric("Energy Availability (EA)", f"{round(ea, 1)} kcal/kg FFM")
                
                if ea < 30:
                    st.error("⚠️ ACHTUNG: EA unter 30 kcal/kg FFM! Risiko für RED-S und hormonelle Dysregulation.")
                elif ea < 45:
                    st.warning("⚡ Moderater Bereich. Achte darauf, an harten Trainingstagen genug zu essen.")
                else:
                    st.success("🟢 Optimaler Bereich (> 45 kcal/kg FFM). Gute Energieverfügbarkeit für Adaption.")
    else:
        st.error("Fehler beim Abrufen der Daten von Intervals.icu. Bitte prüfe deine Athlete ID und den API Key.")
