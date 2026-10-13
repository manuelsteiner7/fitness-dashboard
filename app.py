import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- SEITEN-KONFIGURATION ---
st.set_page_config(page_title="Performance & Nutrition Dashboard", page_icon="⚡", layout="wide")

st.title("⚡ Performance & Nutrition Dashboard")
st.markdown("Live-Daten von Intervals.icu, automatisierte Makro-Periodisierung & Energy Availability.")

# --- SIDEBAR: AUTHENTIFIZIERUNG & USER-DATEN ---
st.sidebar.header("🔑 API & Einstellungen")

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

ffm_kg = weight_kg * (1 - (body_fat_pct / 100))

st.sidebar.divider()
st.sidebar.header("🚶‍♂️ Schritte & Alltagsaktivität")
steps = st.sidebar.number_input("Tägliche Schritte (Ziel/Ist)", min_value=1000, max_value=30000, value=10000, step=500)

# Zusätzliche Kalorien durch Schritte abschätzen (ca. 0.04 kcal pro Schritt je nach Gewicht)
step_calories = int(steps * 0.04)

# --- API DATEN ABRUFEN ---
if not athlete_id or not api_key:
    st.warning("⚠️ Bitte gib deine Intervals.icu Athlete ID und deinen API Key in der Sidebar ein (oder hinterlege sie in den Streamlit Secrets).")
else:
    auth = ('API_KEY', api_key)
    
    today = datetime.today().date()
    start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date = (today + timedelta(days=3)).strftime('%Y-%m-%d')
    
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
        
        latest_weight = weight_kg
        for w in reversed(wellness_list):
            if 'weight' in w and w['weight']:
                latest_weight = w['weight']
                break

        # --- HAUPTBEREICH: METRIKEN ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Aktuelles Gewicht", f"{latest_weight} kg")
        col2.metric("Berechneter BMR", f"{int(bmr)} kcal")
        col3.metric("Schritte-Kalorien", f"+{step_calories} kcal", delta=f"{steps} Schritte")
        col4.metric("Status API", "Verbunden ✅", delta="Intervals.icu")

        st.divider()

        # --- TÄGLICHE MAKRO- & ZIEL-KACHELN (HEUTE BIS +3 TAGE) ---
        st.subheader("🍽️ Tägliche Ernährungs- & Makro-Ziele (Periodisiert)")
        
        # Wir zeigen die nächsten 4 Tage an (Heute + 3 Tage)
        day_cols = st.columns(4)
        
        for i in range(4):
            target_date = today + timedelta(days=i)
            date_str = target_date.strftime('%Y-%m-%d')
            day_name = "Heute" if i == 0 else target_date.strftime('%d.%m. (%a)')
            
            # Finde Events für diesen Tag, um den TSS / Workload zu ermitteln
            day_events = [e for e in events_list if e.get('start_date_local', '').startswith(date_str)]
            day_load = sum([e.get('icu_training_load', 0) or 0 for e in day_events])
            day_duration = sum([e.get('moving_time', 0) or 0 for e in day_events]) / 60 # Minuten
            
            # Makro-Logik je nach Belastung
            # Protein fix hoch für Muskelaufbau/Erhalt: ca. 2.0g - 2.2g pro kg FFM oder 1.8g pro kg Körpergewicht (~150g)
            protein_target = int(weight_kg * 2.0) 
            
            # Fett: ca. 1.0g pro kg Körpergewicht (~70-80g)
            fat_target = int(weight_kg * 1.1)
            
            # Kohlenhydrate basierend auf Trainingstag-Härte
            if day_load > 120 or day_duration > 120:
                carbs_target = int(weight_kg * 9) # Hard day
                activity_label = "🔥 Hartes Training"
            elif day_load > 60 or day_duration > 60:
                carbs_target = int(weight_kg * 6) # Moderates Training
                activity_label = "⚡ Moderates Training"
            else:
                carbs_target = int(weight_kg * 4) # Ruhetag / Z2
                activity_label = "🟢 Rest / Z2"

            # Kalorien-Berechnung: BMR + NEAT (Schritte) + TEF (~10%) + Aktivitätskalorien (geschätzt über TSS * 8 oder direkt)
            est_exercise_cals = int(day_load * 8) if day_load > 0 else 300
            total_target_cals = int(bmr + step_calories + est_exercise_cals)
            
            # Fallback falls gewünschter Bereich (z.B. bei sehr hohem Volumen Richtung 5000-8000 kcal)
            with day_cols[i]:
                st.markdown(f"### {day_name}")
                st.caption(activity_label)
                st.metric("Ziel-Kalorien", f"{total_target_cals} kcal")
                st.markdown(f"""
                * **Kohlenhydrate:** `{carbs_target} g`
                * **Protein:** `{protein_target} g`
                * **Fett:** `{fat_target} g`
                * *TSS:* `{int(day_load)}`
                """)

        st.divider()

        # --- WORKOUTS IN OFFENEN KACHELN ---
        st.subheader("📅 Anstehende Workouts & Trainingseinheiten (Details)")
        
        future_events = [e for e in events_list if e.get('start_date_local', '') >= str(today)]
        
        if future_events:
            for ev in future_events:
                ev_name = ev.get('name', 'Training')
                ev_date = ev.get('start_date_local', '').split('T')[0]
                ev_type = ev.get('type', 'Ride')
                moving_time = int(ev.get('moving_time', 0) / 60) # Minuten
                planned_load = int(ev.get('icu_training_load', 0) or 0)
                description = ev.get('description', 'Keine Beschreibung hinterlegt.')
                
                # Fueling Empfehlung
                if planned_load > 100 or moving_time > 90:
                    fuel_advice = "🚀 **Intra-Workout:** ~90g+ Kohlenhydrate / Stunde (Gels/Drink)."
                elif planned_load > 50:
                    fuel_advice = "⚡ **Intra-Workout:** ~60g Kohlenhydrate / Stunde."
                else:
                    fuel_advice = "💧 **Intra-Workout:** Wasser & Elektrolyte ausreichend."

                # Als offene Box / Kachel darstellen statt expander
                with st.container(border=True):
                    col_w1, col_w2 = st.columns([3, 1])
                    with col_w1:
                        st.markdown(f"#### 🚴‍♂️ {ev_date}: {ev_name} (`{ev_type}`)")
                        st.markdown(f"**Inhalt / Beschreibung:**\n\n {description}")
                        st.info(fuel_advice)
                    with col_w2:
                        st.metric("Geplante Dauer", f"{moving_time} min")
                        st.metric("Training Load", f"{planned_load} TSS")
        else:
            st.info("Keine zukünftigen Events im abgefragten Zeitraum gefunden.")

        # --- ENERGY AVAILABILITY RECHNER ---
        st.divider()
        st.subheader("🔋 Energy Availability (EA) Rechner (Heutiger Stand)")
        
        col_ea1, col_ea2 = st.columns(2)
        with col_ea1:
            consumed_cals = st.number_input("Gegessene Kalorien heute (kcal)", value=3200, step=100)
            exercise_cals = st.number_input("Verbrauchte Trainingskalorien heute (kcal)", value=800, step=50)
        
        with col_ea2:
            if ffm_kg > 0:
                ea = (consumed_cals - exercise_cals) / ffm_kg
                st.metric("Energy Availability (EA)", f"{round(ea, 1)} kcal/kg FFM")
                
                if ea < 30:
                    st.error("⚠️ ACHTUNG: EA unter 30 kcal/kg FFM! Risiko für RED-S.")
                elif ea < 45:
                    st.warning("⚡ Moderater Bereich. An harten Tagen auf genügend Zufuhr achten.")
                else:
                    st.success("🟢 Optimaler Bereich (> 45 kcal/kg FFM). Top Energieverfügbarkeit!")
    else:
        st.error("Fehler beim Abrufen der Daten von Intervals.icu. Bitte prüfe deine Athlete ID und den API Key.")
