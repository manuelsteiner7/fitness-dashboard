import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- SEITEN-KONFIGURATION ---
st.set_page_config(page_title="Performance & Nutrition Dashboard", page_icon="⚡", layout="wide")

st.title("⚡ Performance & Nutrition Dashboard")
st.markdown("Live-Daten von Intervals.icu, automatische Makro-Periodisierung & Energy Availability.")

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
        # Abrufen der bereits absolvierten Aktivitäten (für echte Kalorien vergangener Workouts)
        a_res = requests.get(f"https://intervals.icu/api/v1/athlete/{a_id}/activities?oldest={start}&newest={end}", auth=auth_tuple)
        
        w_data = w_res.json() if w_res.status_code == 200 else []
        e_data = e_res.json() if e_res.status_code == 200 else []
        a_data = a_res.json() if a_res.status_code == 200 else []
        return w_data, e_data, a_data, w_res.status_code, e_res.status_code, a_res.status_code

    wellness_list, events_list, activities_list, status_w, status_e, status_a = fetch_intervals_data(athlete_id, api_key, start_date, end_date)

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
        
        day_cols = st.columns(4)
        
        for i in range(4):
            target_date = today + timedelta(days=i)
            date_str = target_date.strftime('%Y-%m-%d')
            day_name = "Heute" if i == 0 else target_date.strftime('%d.%m. (%a)')
            
            # Prüfen ob Tag in der Vergangenheit/heute liegt oder in der Zukunft
            is_past_or_today = target_date <= today
            
            if is_past_or_today:
                # Echte absolvierte Aktivitäten für diesen Tag filtern (start_date_local enthält das Datum)
                day_acts = [a for a in activities_list if a.get('start_date_local', '').startswith(date_str)]
                # Kalorien aus Aktivitäten (entweder 'calories' oder 'icu_joules' / 4.184)
                actual_cals = 0
                for act in day_acts:
                    c = act.get('calories')
                    if c:
                        actual_cals += c
                    else:
                        # Fallback über Kilojoule (1 kJ = 0.239 kcal)
                        kJ = act.get('icu_joules') or act.get('energy')
                        if kJ:
                            actual_cals += int(kJ / 4.184)
                
                est_exercise_cals = actual_cals
                day_load = sum([a.get('icu_training_load', 0) or 0 for a in day_acts])
                day_duration = sum([a.get('moving_time', 0) or 0 for a in day_acts]) / 60
                activity_label = f"✅ Erfasst ({len(day_acts)} Einheit(en))" if day_acts else "🟢 Ruhetag / Kein Upload"
            else:
                # Zukünftige Events (Geplant)
                day_events = [e for e in events_list if e.get('start_date_local', '').startswith(date_str)]
                day_load = sum([e.get('icu_training_load', 0) or 0 for e in day_events])
                day_duration = sum([e.get('moving_time', 0) or 0 for e in day_events]) / 60
                # Schätzung für geplante Events über TSS (* 8 als Daumenregel oder Event-Daten)
                est_exercise_cals = int(day_load * 8) if day_load > 0 else 300
                
                if day_load > 120 or day_duration > 120:
                    activity_label = "🔥 Hartes Training (Geplant)"
                elif day_load > 60 or day_duration > 60:
                    activity_label = "⚡ Moderates Training (Geplant)"
                else:
                    activity_label = "🟢 Rest / Z2 (Geplant)"

            # Makros berechnen
            protein_target = int(weight_kg * 2.0)
            fat_target = int(weight_kg * 1.1)
            
            if day_load > 120 or day_duration > 120:
                carbs_target = int(weight_kg * 9)
            elif day_load > 60 or day_duration > 60:
                carbs_target = int(weight_kg * 6)
            else:
                carbs_target = int(weight_kg * 4)

            # Gesamtbedarf (Erhaltungsumsatz für diesen Tag bei 0-Linie)
            total_target_cals = int(bmr + step_calories + est_exercise_cals)
            
            with day_cols[i]:
                st.markdown(f"### {day_name}")
                st.caption(activity_label)
                st.metric("Ziel-Kalorien", f"{total_target_cals} kcal")
                st.markdown(f"""
                * **Kohlenhydrate:** `{carbs_target} g`
                * **Protein:** `{protein_target} g`
                * **Fett:** `{fat_target} g`
                * *Aktivitäts-kcal:* `{est_exercise_cals}`
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
                moving_time = int(ev.get('moving_time', 0) / 60)
                planned_load = int(ev.get('icu_training_load', 0) or 0)
                description = ev.get('description', 'Keine Beschreibung hinterlegt.')
                
                if planned_load > 100 or moving_time > 90:
                    fuel_advice = "🚀 **Intra-Workout:** ~90g+ Kohlenhydrate / Stunde (Gels/Drink)."
                elif planned_load > 50:
                    fuel_advice = "⚡ **Intra-Workout:** ~60g Kohlenhydrate / Stunde."
                else:
                    fuel_advice = "💧 **Intra-Workout:** Wasser & Elektrolyte ausreichend."

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
        
        # Versuche die heutigen echten Aktivitäts-Kalorien für den EA Rechner vorauszufüllen
        today_str = today.strftime('%Y-%m-%d')
        today_acts = [a for a in activities_list if a.get('start_date_local', '').startswith(today_str)]
        default_real_cals = sum([a.get('calories') or int((a.get('icu_joules') or 0)/4.184) for a in today_acts])
        if default_real_cals == 0:
            default_real_cals = 800 # Fallback

        col_ea1, col_ea2 = st.columns(2)
        with col_ea1:
            consumed_cals = st.number_input("Gegessene Kalorien heute (kcal)", value=3200, step=100)
            exercise_cals = st.number_input("Verbrauchte Trainingskalorien heute (aus Intervals)", value=default_real_cals, step=50)
        
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
