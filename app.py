import streamlit as st
import requests
import pandas as pd
import json
import re
from datetime import datetime, timedelta

# --- SEITEN-KONFIGURATION ---
st.set_page_config(page_title="Performance & Nutrition Dashboard", page_icon="⚡", layout="wide")

st.title("⚡ Performance & Nutrition Dashboard")
st.markdown("Live-Daten von Intervals.icu, Energiebilanz, EA-Rechner & KI-Coach.")

# --- SIDEBAR: AUTHENTIFIZIERUNG & EINSTELLUNGEN ---
st.sidebar.header("🔑 API & Einstellungen")

if "athlete_id" not in st.session_state:
    st.session_state.athlete_id = st.secrets["INTERVALS_ATHLETE_ID"] if "INTERVALS_ATHLETE_ID" in st.secrets else ""
if "api_key" not in st.session_state:
    st.session_state.api_key = st.secrets["INTERVALS_API_KEY"] if "INTERVALS_API_KEY" in st.secrets else ""
if "claude_api_key" not in st.session_state:
    st.session_state.claude_api_key = st.secrets["ANTHROPIC_API_KEY"] if "ANTHROPIC_API_KEY" in st.secrets else ""

with st.sidebar.expander("🔐 Zugangsdaten konfigurieren", expanded=not (st.session_state.athlete_id and st.session_state.api_key)):
    st.session_state.athlete_id = st.text_input("Intervals Athlete ID", value=st.session_state.athlete_id, type="default")
    st.session_state.api_key = st.text_input("Intervals API Key", value=st.session_state.api_key, type="password")
    st.session_state.claude_api_key = st.text_input("Anthropic (Claude) API Key", value=st.session_state.claude_api_key, type="password")

athlete_id = st.session_state.athlete_id
api_key = st.session_state.api_key
claude_api_key = st.session_state.claude_api_key

st.sidebar.divider()
st.sidebar.header("👤 Biometrische Daten")
weight_kg = st.sidebar.number_input("Körpergewicht (kg)", value=72.0, step=0.5)
body_fat_pct = st.sidebar.slider("Körperfettanteil (%)", min_value=5.0, max_value=30.0, value=11.0, step=0.5)
age = st.sidebar.number_input("Alter", value=31, step=1)
height_cm = st.sidebar.number_input("Größe (cm)", value=184, step=1)
gender = st.sidebar.selectbox("Geschlecht", ["Männlich", "Weiblich"])

if gender == "Männlich":
    bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
else:
    bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

ffm_kg = weight_kg * (1 - (body_fat_pct / 100))

st.sidebar.divider()
st.sidebar.header("🚶‍♂️ Schritte & Alltagsaktivität")
steps = st.sidebar.number_input("Tägliche Schritte (Heute)", min_value=1000, max_value=30000, value=10000, step=500)
step_calories = int(steps * 0.04)

today = datetime.today().date()
today_str = today.strftime('%Y-%m-%d')

# --- HILFSFUNKTIONEN FÜR PERSISTENZ IN INTERVALS.ICU ---
def save_meals_to_intervals(a_id, a_key, date_str, meals_list):
    auth_tuple = ('API_KEY', a_key)
    url = f"https://intervals.icu/api/v1/athlete/{a_id}/wellness/{date_str}"
    data_str = json.dumps(meals_list)
    payload = {"comments": f"LOGGED_MEALS:{data_str}"}
    requests.put(url, json=payload, auth=auth_tuple)

def create_intervals_event(a_id, a_key, date_str, name, workout_type, description):
    auth_tuple = ('API_KEY', a_key)
    url = f"https://intervals.icu/api/v1/athlete/{a_id}/events"
    payload = {
        "start_date_local": f"{date_str}T00:00:00",
        "name": name,
        "type": workout_type,
        "description": description
    }
    res = requests.post(url, json=payload, auth=auth_tuple)
    return res.status_code in [200, 201], res.text

# --- API DATEN ABRUFEN ---
if not athlete_id or not api_key:
    st.warning("⚠️ Bitte hinterlege deine Intervals.icu Athlete ID und deinen API Key in der Sidebar unter den Einstellungen.")
else:
    start_date = (today - timedelta(days=6)).strftime('%Y-%m-%d')
    end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
    
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

        # Geloggte Mahlzeiten beim Start automatisch aus Intervals.icu auslesen
        if "logged_meals" not in st.session_state:
            st.session_state.logged_meals = []
            today_wellness = [w for w in wellness_list if w.get('id') == today_str]
            if today_wellness and 'comments' in today_wellness[0]:
                comments = today_wellness[0]['comments'] or ""
                if "LOGGED_MEALS:" in comments:
                    try:
                        raw_json = comments.split("LOGGED_MEALS:")[1]
                        st.session_state.logged_meals = json.loads(raw_json)
                    except Exception:
                        pass

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
            
            raw_moving_time = selected_ev.get('moving_time')
            moving_time = int(raw_moving_time / 60) if raw_moving_time is not None else 0
            
            raw_load = selected_ev.get('icu_training_load')
            planned_load = int(raw_load) if raw_load is not None else 0
            
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
        # --- MAHLZEITEN-SCHÄTZUNG VIA FORMULAR ---
        # ==========================================
        st.subheader("🍽️ Mahlzeit eintragen (Automatische KI-Nährwertanalyse)")
        st.markdown("Tippe deine Zutaten ein und drücke **Enter**, um die Nährwerte einzeln aufzuschlüsseln.")

        with st.form(key="meal_form", clear_on_submit=True):
            col_meal1, col_meal2 = st.columns([3, 1])
            with col_meal1:
                meal_input = st.text_input("Mahlzeit / Zutaten", placeholder="z. B. '70g Haferflocken, 10g dunkle Schokolade, 5g Honig'")
            with col_meal2:
                st.write("")
                st.write("")
                analyze_btn = st.form_submit_button("➕ Schätzen & Eintragen", use_container_width=True)

        if analyze_btn and meal_input:
            if not claude_api_key:
                st.error("Bitte hinterlege deinen Anthropic API Key in der Sidebar.")
            else:
                with st.spinner("Haiku analysiert und schlüsselt die Zutaten einzeln auf..."):
                    try:
                        headers = {
                            "x-api-key": claude_api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        }
                        
                        prompt_analysis = f"""
Du bist der Ernährungsberater von Manuel Steiner.
Berechne die Nährwerte für folgende Mahlzeit/Zutaten (Rohgewichte): "{meal_input}".

Nutze Manuels Produktdaten falls zutreffend:
- HSN Sojaprotein (100g): 389 kcal, 1.4g KH, 92g Protein, 1.8g Fett
- Crunch Müsli (100g): 364 kcal, 64g KH, 9.5g Protein, 6g Fett
- Kantinenpizza (1/4 Pizza, 2 Stk): 620 kcal, 83g KH, 26g Protein, 18g Fett

Drösele alle eingegebenen Zutaten EINZELN auf!
Antworte AUSSCHLIESSLICH als ein valides JSON-Array von Objekten ohne Begleittext oder Markdown-Codeblöcke:
[
  {{
    "calories": 260,
    "carbs": 42,
    "protein": 9,
    "fat": 5,
    "summary": "70g Haferflocken"
  }}
]
"""
                        payload = {
                            "model": "claude-haiku-4-5-20251001",
                            "max_tokens": 500,
                            "messages": [{"role": "user", "content": prompt_analysis}]
                        }
                        
                        res = requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
                        if res.status_code == 200:
                            raw_text = res.json()['content'][0]['text']
                            cleaned_json_match = re.search(r'\[.*\]', raw_text, re.DOTALL) or re.search(r'\{.*\}', raw_text, re.DOTALL)
                            if cleaned_json_match:
                                json_str = cleaned_json_match.group(0)
                                data = json.loads(json_str)
                                if isinstance(data, list):
                                    st.session_state.logged_meals.extend(data)
                                else:
                                    st.session_state.logged_meals.append(data)
                                
                                # In Intervals.icu dauerhaft sichern
                                save_meals_to_intervals(athlete_id, api_key, today_str, st.session_state.logged_meals)
                                st.rerun()
                            else:
                                st.error(f"Konnte Nährwerte nicht parsen. Antwort war: {raw_text}")
                        else:
                            st.error(f"Fehler bei der API-Anfrage ({res.status_code}): {res.text}")
                    except Exception as e:
                        st.error(f"Fehler beim Verarbeiten: {e}")

        # ==========================================
        # --- HEUTIGER TAG HERO-SEKTION ---
        # ==========================================
        st.divider()
        st.subheader("🎯 Heutiger Tag – Live Energie- & Makro-Übersicht")
        
        today_acts = [a for a in activities_list if a.get('start_date_local', '').startswith(today_str)]
        
        today_exercise_cals = 0
        for act in today_acts:
            c = act.get('calories')
            if not c:
                kJ = act.get('icu_joules') or act.get('energy')
                c = int(kJ / 4.184) if kJ else 0
            today_exercise_cals += c

        total_today_output = int(bmr + step_calories + today_exercise_cals)

        consumed_today = int(sum(m.get('calories', 0) for m in st.session_state.logged_meals))
        total_carbs = round(sum(m.get('carbs', 0) for m in st.session_state.logged_meals), 1)
        total_protein = round(sum(m.get('protein', 0) for m in st.session_state.logged_meals), 1)
        total_fat = round(sum(m.get('fat', 0) for m in st.session_state.logged_meals), 1)

        st.markdown(f"**Aktuelles Gewicht:** `{latest_weight} kg` | **Magermasse (FFM):** `{round(ffm_kg, 1)} kg`")

        net_balance = consumed_today - total_today_output
        energy_availability = (consumed_today - today_exercise_cals) / ffm_kg if ffm_kg > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Gesamtverbrauch (TDEE)", f"{total_today_output} kcal", delta=f"BMR {int(bmr)} + NEAT {step_calories} + Training {today_exercise_cals}")
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

        m1, m2, m3 = st.columns(3)
        m1.metric("Kohlenhydrate (KH)", f"{total_carbs} g")
        m2.metric("Protein", f"{total_protein} g", delta=f"Ziel: ~145-155g")
        m3.metric("Fett", f"{total_fat} g")

        if st.session_state.logged_meals:
            with st.expander("📋 Geloggte Einzelzutaten heute anzeigen", expanded=True):
                for idx, m in enumerate(reversed(st.session_state.logged_meals)):
                    st.markdown(f"• **{m.get('summary')}**: `{m.get('calories')} kcal` | KH: `{m.get('carbs')}g` | Prot: `{m.get('protein')}g` | Fett: `{m.get('fat')}g`")
                if st.button("🗑️ Geloggte Mahlzeiten zurücksetzen"):
                    st.session_state.logged_meals = []
                    save_meals_to_intervals(athlete_id, api_key, today_str, [])
                    st.rerun()

        st.divider()

        # ==========================================
        # --- INTERAKTIVE WOCHEN-ÜBERSICHT ---
        # ==========================================
        st.subheader("📊 Interaktive Wochen-Übersicht (Bilanz & EA)")

        week_data = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            d_str = d.strftime('%Y-%m-%d')
            d_name = d.strftime('%a %d.%m.')
            
            day_acts = [a for a in activities_list if a.get('start_date_local', '').startswith(d_str)]
            ex_cals = sum([a.get('calories') or int((a.get('icu_joules') or 0)/4.184) for a in day_acts])
            
            day_output = int(bmr + step_calories + ex_cals)
            
            # Aus den Wellness-Einträgen vergangener Tage gegessene Kalorien laden
            past_intake = 2800
            day_wellness = [w for w in wellness_list if w.get('id') == d_str]
            if day_wellness and 'comments' in day_wellness[0]:
                c_str = day_wellness[0]['comments'] or ""
                if "LOGGED_MEALS:" in c_str:
                    try:
                        p_meals = json.loads(c_str.split("LOGGED_MEALS:")[1])
                        past_intake = sum(m.get('calories', 0) for m in p_meals)
                    except Exception:
                        pass
            
            day_intake = consumed_today if i == 0 else past_intake
            
            week_data.append({
                "Datum": d_name,
                "Verbrauch (TDEE)": day_output,
                "Intake (kcal)": day_intake,
                "Training Cals": ex_cals
            })

        df_week = pd.DataFrame(week_data)

        df_week["Bilanz"] = df_week["Intake (kcal)"] - df_week["Verbrauch (TDEE)"]
        df_week["EA (kcal/kg FFM)"] = ((df_week["Intake (kcal)"] - df_week["Training Cals"]) / ffm_kg).round(1)

        st.dataframe(df_week, use_container_width=True, hide_index=True)

        tot_verbrauch = df_week["Verbrauch (TDEE)"].sum()
        tot_intake = df_week["Intake (kcal)"].sum()
        tot_bilanz = df_week["Bilanz"].sum()
        avg_ea = df_week["EA (kcal/kg FFM)"].mean()

        col_w1, col_w2, col_w3, col_w4 = st.columns(4)
        col_w1.metric("Wochen-Verbrauch", f"{tot_verbrauch} kcal")
        col_w2.metric("Wochen-Intake", f"{tot_intake} kcal")
        col_w3.metric("Wochen-Bilanz", f"{tot_bilanz} kcal")
        col_w4.metric("Ø Energy Availability", f"{round(avg_ea, 1)} kcal/kg")

        st.divider()

        # ==========================================
        # --- CLAUDE KI-COACH CHAT MIT INTERVALS-PUSH ---
        # ==========================================
        st.subheader("💬 Claude AI Performance & Nutrition Coach (Sonnet)")
        st.markdown("Frag Claude zu deinen Live-Werten, Wochenbilanzen oder fordere Workouts an, die du direkt in den Kalender übertragen kannst.")

        if not claude_api_key:
            st.info("💡 Trage deinen Anthropic API-Key in der Sidebar unter den Einstellungen ein, um den Chat zu aktivieren.")
        else:
            if "messages" not in st.session_state:
                st.session_state.messages = []

            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input("Frage deinen Performance & Nutrition Coach..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    with st.spinner("Claude analysiert deine Daten..."):
                        try:
                            headers = {
                                "x-api-key": claude_api_key,
                                "anthropic-version": "2023-06-01",
                                "content-type": "application/json"
                            }
                            
                            system_context = (
                                "Du bist der persönliche Ausdauercoach (Rennrad und Marathon) für Manuel Steiner.\n\n"
                                "### DATENZUGRIFF & LIVE-STATUS\n"
                                "Du hast direkten Zugriff auf die Live-Daten des Athleten, die dir hier übergeben werden. "
                                "Beantworte Fragen direkt anhand dieser Daten und sage niemals, dass du keinen Zugriff auf den Account hast.\n\n"
                                "### COACHING- UND KOMMUNIKATIONSSTIL\n"
                                "* Biete eine wissenschaftlich fundierte, evidenzbasierte Begründung anhand der Trainingsphysiologie.\n"
                                "* Objektive, rationale Antworten, keine unbegründete Zustimmung. Korrigiere fachlich nicht sinnvolle Einschätzungen direkt.\n"
                                "* Klares, natürliches Deutsch. Unnötige englische Begriffe vermeiden.\n"
                                "* Gedankenstriche NIEMALS als Ersatz für Kommata oder Satzzeichen verwenden.\n"
                                "* Bei Wochenplänen den genauen Inhalt der Workouts angeben (Intervallzeiten inkl. exakter Wattzahlen, HF-Bereiche, Pace beim Laufen).\n\n"
                                "### WORKOUT-PUSHER PROTOKOLL\n"
                                "WENN der Athlet dich bittet, ein Workout zu planen oder in den Kalender einzutragen, füge am Ende deiner Antwort IMMER genau folgenden JSON-Block ein:\n\n"
                                "```json_workout\n"
                                "{\n"
                                '  "date": "YYYY-MM-DD",\n'
                                '  "name": "4x10m Sweet Spot",\n'
                                '  "type": "Ride",\n'
                                '  "description": "- 15m Z2\\n- 4x 10m @ 285W (5m Z1)\\n- 15m Z1"\n'
                                "}\n"
                                "```\n\n"
                                "### ATHLETENPROFIL & BENCHMARKS\n"
                                "* Name: Manuel Steiner, Enterprise Architect bei SAP in München, 1,84 m, ~72 kg.\n"
                                "* Rennrad: FTP 319 W, 5-Minuten-Leistung 379 W, Schwellen-HF 169 bpm.\n"
                                "* Laufen: Schwellenpace 3:42 min/km, Schwellen-HF 173 bpm.\n\n"
                                f"### AKTUELLE LIVE-DATEN (HEUTE & WOCHE)\n"
                                f"* TDEE: {total_today_output} kcal | Gegessen: {consumed_today} kcal (KH: {total_carbs}g, Prot: {total_protein}g, Fett: {total_fat}g).\n"
                                f"* Bilanz: {net_balance} kcal | EA: {round(energy_availability, 1)} kcal/kg FFM.\n"
                                f"* Anstehende Workouts im Kalender: {[e.get('name') + ' (' + e.get('start_date_local','').split('T')[0] + ')' for e in future_events]}\n"
                                f"* Wochenübersicht:\n{df_week.to_string()}"
                            )

                            payload = {
                                "model": "claude-sonnet-4-6",
                                "max_tokens": 1024,
                                "system": system_context,
                                "messages": [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                            }
                            
                            response = requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
                            res_json = response.json()
                            
                            if response.status_code == 200:
                                bot_reply = res_json['content'][0]['text']
                                st.markdown(bot_reply)
                                
                                # Workout-Erkennung für Intervals.icu
                                if "```json_workout" in bot_reply:
                                    try:
                                        workout_json_str = bot_reply.split("```json_workout")[1].split("```")[0].strip()
                                        w_data = json.loads(workout_json_str)
                                        
                                        st.info(f"📅 Workout erkannt: **{w_data.get('name')}** am `{w_data.get('date')}`")
                                        if st.button("🚀 Workout direkt in Intervals.icu eintragen", key="push_workout_btn"):
                                            success, resp = create_intervals_event(
                                                athlete_id, api_key,
                                                w_data.get('date'),
                                                w_data.get('name'),
                                                w_data.get('type', 'Ride'),
                                                w_data.get('description', '')
                                            )
                                            if success:
                                                st.success("✅ Workout erfolgreich in deinen Intervals.icu Kalender eingetragen!")
                                            else:
                                                st.error(f"Fehler beim Erstellen: {resp}")
                                    except Exception as e:
                                        st.warning(f"Konnte Workout-JSON nicht parsen: {e}")

                                st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                            else:
                                err_msg = res_json.get('error', {}).get('message', str(res_json))
                                st.error(f"API-Fehler ({response.status_code}): {err_msg}")
                        except Exception as e:
                            st.error(f"Fehler: {e}")

    else:
        st.error("Fehler beim Abrufen der Intervals.icu Daten. Bitte prüfe ID und API Key.")
