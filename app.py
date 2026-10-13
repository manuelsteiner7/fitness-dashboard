import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- SEITEN-KONFIGURATION ---
st.set_page_config(page_title="Performance & Nutrition Dashboard", page_icon="⚡", layout="wide")

st.title("⚡ Performance & Nutrition Dashboard")
st.markdown("Live-Daten von Intervals.icu, Energiebilanz, EA-Rechner & KI-Coach.")

# --- SIDEBAR: AUTHENTIFIZIERUNG & EINSTELLUNGEN ---
st.sidebar.header("🔑 API & Einstellungen")

sec_athlete = st.secrets["INTERVALS_ATHLETE_ID"] if "INTERVALS_ATHLETE_ID" in st.secrets else ""
sec_intervals_key = st.secrets["INTERVALS_API_KEY"] if "INTERVALS_API_KEY" in st.secrets else ""
sec_claude_key = st.secrets["ANTHROPIC_API_KEY"] if "ANTHROPIC_API_KEY" in st.secrets else ""

with st.sidebar.expander("🔐 Zugangsdaten konfigurieren", expanded=not (sec_athlete and sec_intervals_key)):
    athlete_id = st.text_input("Intervals Athlete ID", value=sec_athlete, type="default")
    api_key = st.text_input("Intervals API Key", value=sec_intervals_key, type="password")
    claude_api_key = st.text_input("Anthropic (Claude) API Key", value=sec_claude_key, type="password")

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
steps = st.sidebar.number_input("Tägliche Schritte (Heute)", min_value=1000, max_value=30000, value=10000, step=500)
step_calories = int(steps * 0.04)

# --- API DATEN ABRUFEN ---
if not athlete_id or not api_key:
    st.warning("⚠️ Bitte hinterlege deine Intervals.icu Athlete ID und deinen API Key in der Sidebar unter den Einstellungen.")
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

        # ==========================================
        # --- HEUTIGER TAG: DETAILLIERTE HERO-SEKTION ---
        # ==========================================
        st.subheader("🎯 Heutiger Tag – Live Energie- & Bilanz-Übersicht")
        
        today_str = today.strftime('%Y-%m-%d')
        today_acts = [a for a in activities_list if a.get('start_date_local', '').startswith(today_str)]
        
        # Echte Aktivitätskalorien heute aus Intervals sammeln + Details der Einheiten
        today_exercise_cals = 0
        workout_details_list = []
        for act in today_acts:
            act_name = act.get('name', 'Training')
            c = act.get('calories')
            if not c:
                kJ = act.get('icu_joules') or act.get('energy')
                c = int(kJ / 4.184) if kJ else 0
            today_exercise_cals += c
            workout_details_list.append(f"• **{act_name}**: `{c} kcal`")

        # Gesamterbrauch heute = BMR + Schritte (NEAT) + Echte Workout-Kalorien (TEF wird meist vernachlässigt oder pauschal addiert)
        total_today_output = int(bmr + step_calories + today_exercise_cals)

        # Eingabe für den Intake (Gegessene Kalorien heute)
        col_in1, col_in2 = st.columns([2, 2])
        with col_in1:
            consumed_today = st.number_input("Gegessene Kalorien heute (Intake in kcal)", value=3200, step=50)
        with col_in2:
            st.markdown(f"**Aktuelles Gewicht:** `{latest_weight} kg` | **Magermasse (FFM):** `{round(ffm_kg, 1)} kg`")

        # Gegenrechnung: Bilanz (Intake - Output)
        net_balance = consumed_today - total_today_output

        # Exakte EA Berechnung: (Intake - Exercise Energy Expenditure) / FFM
        # Hinweis: EA bezieht sich rein auf den Kraftstoff nach Abzug der Sportkalorien
        energy_availability = (consumed_today - today_exercise_cals) / ffm_kg if ffm_kg > 0 else 0

        # Große KPI-Kacheln für den heutigen Tag
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Gesamtverbrauch (TDEE)", f"{total_today_output} kcal", delta=f"BMR {int(bmr)} + NEAT {step_calories} + Workouts {today_exercise_cals}")
        c2.metric("Gegessen (Intake)", f"{consumed_today} kcal")
        
        if net_balance >= 0:
            c3.metric("Bilanz", f"+{net_balance} kcal", delta="Überschuss", delta_color="normal")
        else:
            c3.metric("Bilanz", f"{net_balance} kcal", delta="Defizit", delta_color="inverse")

        if energy_availability < 30:
            c4.metric("Energy Availability", f"{round(energy_availability, 1)} kcal/kg", delta="⚠️ Kritisch (<30)", delta_color="inverse")
        elif energy_availability < 45:
            c4.metric("Energy Availability", f"{round(energy_availability, 1)} kcal/kg", delta="⚡ Moderat", delta_color="off")
        else:
            c4.metric("Energy Availability", f"{round(energy_availability, 1)} kcal/kg", delta="🟢 Optimal (>45)", delta_color="normal")
