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
    end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
    
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

        # --- ANSTEHENDE WORKOUTS IN DER SIDEBAR ---
        future_events = [e for e in events_list if e.get('start_date_local', '') >= str(today)]
        
        st.sidebar.divider()
        st.sidebar.header("📅 Anstehende Workouts")
        
        if future_events:
            workout_options = {
                f"{ev.get('start_date_local', '').split('T')[0]} - {ev.get('name', 'Training')}": ev 
                for ev in future_events
            }
            selected_workout_label = st.sidebar.selectbox("Workout auswählen:", list(workout_options.keys()))
            selected_ev = workout_options[selected_workout_label]
            
            ev_name = selected_ev.get('name', 'Training')
            ev_date = selected_ev.get('start_date_local', '').split('T')[0]
            ev_type = selected_ev.get('type', 'Ride')
            moving_time = int(selected_ev.get('moving_time', 0) / 60)
            planned_load = int(selected_ev.get('icu_training_load', 0) or 0)
            description = selected_ev.get('description', 'Keine Beschreibung hinterlegt.')
            
            fuel_advice = "🚀 ~90g+ Carbs/h" if (planned_load > 100 or moving_time > 90) else ("⚡ ~60g Carbs/h" if planned_load > 50 else "💧 Nur Wasser/Elektrolyte")

            with st.sidebar.expander(f"🔍 Details: {ev_name}", expanded=True):
                st.markdown(f"**Datum:** `{ev_date}` | **Typ:** `{ev_type}`")
                st.markdown(f"**Dauer:** `{moving_time} min` | **TSS:** `{planned_load}`")
                st.markdown(f"**Inhalt:**\n{description}")
                st.info(f"**Fueling:** {fuel_advice}")
        else:
            st.sidebar.info("Keine anstehenden Events im Kalender.")

        # ==========================================
        # --- HAUPTSEITE: HEUTIGER TAG HERO-SEKTION ---
        # ==========================================
        st.subheader("🎯 Heutiger Tag – Live Energie- & Bilanz-Übersicht")
        
        today_str = today.strftime('%Y-%m-%d')
        today_acts = [a for a in activities_list if a.get('start_date_local', '').startswith(today_str)]
        
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

        total_today_output = int(bmr + step_calories + today_exercise_cals)

        col_in1, col_in2 = st.columns([2, 2])
        with col_in1:
            consumed_today = st.number_input("Gegessene Kalorien heute (Intake in kcal)", value=3200, step=50)
        with col_in2:
            st.markdown(f"**Aktuelles Gewicht:** `{latest_weight} kg` | **Magermasse (FFM):** `{round(ffm_kg, 1)} kg`")

        net_balance = consumed_today - total_today_output
        energy_availability = (consumed_today - today_exercise_cals) / ffm_kg if ffm_kg > 0 else 0

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

        with st.expander("🔍 Aufschlüsselung der heutigen Einheiten & Verbraucher"):
            st.markdown(f"- **Grundumsatz (BMR):** `{int(bmr)} kcal`")
            st.markdown(f"- **Alltagsaktivität (Schritte: {steps}):** `+{step_calories} kcal`")
            if workout_details_list:
                st.markdown("- **Absolvierte Workouts (Intervals.icu):**")
                for w_str in workout_details_list:
                    st.markdown(f"  {w_str}")
            else:
                st.info("Heute wurden bisher noch keine abgeschlossenen Aktivitäten via Garmin/Intervals synchronisiert.")

        st.divider()

        # --- TÄGLICHE MAKRO- & ZIEL-KACHELN (4 TAGE) ---
        st.subheader("🍽️ Ernährungs- & Makro-Ziele (Periodisiert)")
        
        day_cols = st.columns(4)
        for i in range(4):
            target_date = today + timedelta(days=i)
            date_str = target_date.strftime('%Y-%m-%d')
            day_name = "Heute" if i == 0 else target_date.strftime('%d.%m. (%a)')
            
            is_past_or_today = target_date <= today
            
            if is_past_or_today:
                day_acts = [a for a in activities_list if a.get('start_date_local', '').startswith(date_str)]
                actual_cals = sum([a.get('calories') or int((a.get('icu_joules') or 0)/4.184) for a in day_acts])
                est_exercise_cals = actual_cals
                day_load = sum([a.get('icu_training_load', 0) or 0 for a in day_acts])
                activity_label = f"✅ Erfasst ({len(day_acts)} Einheit)" if day_acts else "🟢 Ruhetag"
            else:
                day_events = [e for e in events_list if e.get('start_date_local', '').startswith(date_str)]
                day_load = sum([e.get('icu_training_load', 0) or 0 for e in day_events])
                est_exercise_cals = int(day_load * 8) if day_load > 0 else 300
                activity_label = "⚡ Geplant"

            protein_target = int(weight_kg * 2.0)
            fat_target = int(weight_kg * 1.1)
            carbs_target = int(weight_kg * 9) if day_load > 120 else (int(weight_kg * 6) if day_load > 60 else int(weight_kg * 4))
            total_target_cals = int(bmr + step_calories + est_exercise_cals)
            
            with day_cols[i]:
                st.markdown(f"### {day_name}")
                st.caption(activity_label)
                st.metric("Ziel-Kcal (0-Linie)", f"{total_target_cals} kcal")
                st.markdown(f"""
                * **Carbs:** `{carbs_target} g`
                * **Protein:** `{protein_target} g`
                * **Fett:** `{fat_target} g`
                * **Training-Kcal:** `{est_exercise_cals}`
                """)

        # --- CLAUDE KI-COACH CHAT ---
        st.divider()
        st.subheader("💬 Claude AI Performance & Nutrition Coach")
        st.markdown("Frag Claude zu deinen Live-Werten. Er kennt deinen heutigen Verbrauch, den Intake, das Defizit/Überschuss und deine Energy Availability.")

        if not claude_api_key:
            st.info("💡 Trage deinen Anthropic API-Key in der Sidebar unter den Einstellungen ein, um den Chat zu aktivieren.")
        else:
            if "messages" not in st.session_state:
                st.session_state.messages = []

            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input("Frage Claude zu deiner aktuellen Bilanz oder dem Fueling..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    with st.spinner("Claude analysiert deine Live-Bilanz..."):
                        try:
                            headers = {
                                "x-api-key": claude_api_key,
                                "anthropic-version": "2023-06-01",
                                "content-type": "application/json"
                            }
                            
                            system_context = (
                                f"Du bist ein Elite Sport-Nutritionist und Radsport-Trainer. "
                                f"Athleten-Daten: Gewicht {weight_kg}kg, FFM {round(ffm_kg,1)}kg, Grundumsatz (BMR) {int(bmr)} kcal. "
                                f"HEUTIGER TAG LIVE-DATEN: "
                                f"- Schritte-Kalorien (NEAT): {step_calories} kcal ({steps} Schritte) "
                                f"- Echte Workout-Aktivitätskalorien (EEE): {today_exercise_cals} kcal "
                                f"- Gesamterbrauch (TDEE): {total_today_output} kcal "
                                f"- Gegessener Intake: {consumed_today} kcal "
                                f"- Netto-Bilanz: {net_balance} kcal ({'Defizit' if net_balance < 0 else 'Überschuss'}) "
                                f"- Energy Availability (EA): {round(energy_availability, 1)} kcal/kg FFM."
                            )
                            
                            payload = {
                                "model": "claude-3-haiku-20240307",
                                "max_tokens": 1024,
                                "system": system_context,
                                "messages": [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                            }
                            
                            response = requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
                            res_json = response.json()
                            
                            if response.status_code == 200:
                                bot_reply = res_json['content'][0]['text']
                            else:
                                err_msg = res_json.get('error', {}).get('message', str(res_json))
                                bot_reply = f"API-Fehler ({response.status_code}): {err_msg}"
                            
                            st.markdown(bot_reply)
                            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                        except Exception as e:
                            st.error(f"Fehler: {e}")

    else:
        st.error("Fehler beim Abrufen der Intervals.icu Daten. Bitte prüfe ID und API Key.")
