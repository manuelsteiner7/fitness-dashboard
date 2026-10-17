import streamlit as st
import requests
import pandas as pd
import json
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
weight_kg = st.sidebar.number_input("Körpergewicht (kg)", value=73.0, step=0.5)
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

# Session State Initialisierung für den Tages-Intake & Mahlzeiten-Log
if "logged_meals" not in st.session_state:
    st.session_state.logged_meals = []

if "manual_intake_offset" not in st.session_state:
    st.session_state.manual_intake_offset = 0

# --- API DATEN ABRUFEN ---
if not athlete_id or not api_key:
    st.warning("⚠️ Bitte hinterlege deine Intervals.icu Athlete ID und deinen API Key in der Sidebar unter den Einstellungen.")
else:
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
        # --- HEUTIGER TAG HERO-SEKTION ---
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

        # Berechne den aktuellen Tages-Intake aus geloggten Mahlzeiten + Basis-Offset
        consumed_today = st.session_state.manual_intake_offset

        col_in1, col_in2 = st.columns([2, 2])
        with col_in1:
            consumed_today = st.number_input("Gesamter Tages-Intake (kcal)", value=consumed_today, step=50, key="intake_input_field")
            st.session_state.manual_intake_offset = consumed_today
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

        st.divider()

        # ==========================================
        # --- MAHLZEITEN-SCHÄTZUNG & LUNCH LOG ---
        # ==========================================
        st.subheader("🍽️ Mahlzeit eintragen (Automatische KI-Nährwertanalyse)")
        st.markdown("Tippe ein, was du in Gramm gegessen hast. Claude berechnet die Nährwerte und addiert die Kalorien direkt oben zum Intake.")

        col_meal1, col_meal2 = st.columns([3, 1])
        with col_meal1:
            meal_input = st.text_input("Mahlzeit / Zutaten (z. B. '50g Haferflocken, 15g HSN Sojaprotein, 100g Banane')", placeholder="Zutaten in Gramm eingeben...")
        with col_meal2:
            st.write("") # Abstandhalter
            st.write("")
            analyze_btn = st.button("➕ Schätzen & Eintragen", use_container_width=True)

        if analyze_btn and meal_input:
            if not claude_api_key:
                st.error("Bitte hinterlege deinen Anthropic API Key in der Sidebar.")
            else:
                with st.spinner("Claude berechnet Nährwerte & Makros..."):
                    try:
                        headers = {
                            "x-api-key": claude_api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        }
                        
                        prompt_analysis = f"""
Du bist der Ernährungsberater von Manuel Steiner.
Berechne die Nährwerte für folgende Mahlzeit (Rohgewichte): "{meal_input}".

Nutze Manuels Produktdaten falls zutreffend:
- HSN Sojaprotein (100g): 389 kcal, 1.4g KH, 92g Protein, 1.8g Fett
- Crunch Müsli (100g): 364 kcal, 64g KH, 9.5g Protein, 6g Fett
- Kantinenpizza (1/4 Pizza, 2 Stk): 620 kcal, 83g KH, 26g Protein, 18g Fett

Antworte AUSSCHLIESSLICH im folgenden JSON-Format ohne zusätzlichen Text:
{{
    "calories": 350,
    "carbs": 45,
    "protein": 25,
    "fat": 8,
    "summary": "50g Haferflocken + 15g Sojaprotein + 100g Banane"
}}
"""
                        payload = {
                            "model": "claude-3-haiku-20240307",
                            "max_tokens": 300,
                            "messages": [{"role": "user", "content": prompt_analysis}]
                        }
                        
                        res = requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
                        if res.status_code == 200:
                            raw_text = res.json()['content'][0]['text']
                            # JSON Parsen
                            data = json.loads(raw_text.strip())
                            
                            added_cals = int(data.get("calories", 0))
                            st.session_state.manual_intake_offset += added_cals
                            st.session_state.logged_meals.append(data)
                            st.success(f"✅ Hinzugefügt: +{added_cals} kcal | {data.get('carbs')}g KH | {data.get('protein')}g Protein | {data.get('fat')}g Fett")
                            st.rerun()
                        else:
                            st.error(f"Fehler bei der Berechnung: {res.text}")
                    except Exception as e:
                        st.error(f"Fehler: {e}")

        if st.session_state.logged_meals:
            with st.expander("📋 Heute geloggte Mahlzeiten anzeigen", expanded=False):
                for idx, m in enumerate(reversed(st.session_state.logged_meals)):
                    st.markdown(f"• **{m.get('summary')}**: `{m.get('calories')} kcal` (KH: {m.get('carbs')}g | Prot: {m.get('protein')}g | Fett: {m.get('fat')}g)")
                if st.button("🗑️ Geloggte Mahlzeiten zurücksetzen"):
                    st.session_state.logged_meals = []
                    st.session_state.manual_intake_offset = 0
                    st.rerun()

        st.divider()

        # ==========================================
        # --- INTERAKTIVE WOCHEN-TABELLE (INTAKE & BILANZ) ---
        # ==========================================
        st.subheader("📊 Interaktive Wochen-Übersicht (Intake & Bilanz)")
        st.markdown("Passe hier den täglichen Intake an, um sofort die kumulierte Wochenbilanz und die EA-Werte zu sehen.")

        week_data = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            d_str = d.strftime('%Y-%m-%d')
            d_name = d.strftime('%a %d.%m.')
            
            day_acts = [a for a in activities_list if a.get('start_date_local', '').startswith(d_str)]
            ex_cals = sum([a.get('calories') or int((a.get('icu_joules') or 0)/4.184) for a in day_acts])
            
            day_output = int(bmr + step_calories + ex_cals)
            
            week_data.append({
                "Datum": d_name,
                "Verbrauch (TDEE)": day_output,
                "Intake (kcal)": 2800 if i > 0 else consumed_today,
                "Training Cals": ex_cals
            })

        df_week = pd.DataFrame(week_data)
        
        edited_df = st.data_editor(df_week, num_rows="fixed", use_container_width=True)

        edited_df["Bilanz"] = edited_df["Intake (kcal)"] - edited_df["Verbrauch (TDEE)"]
        edited_df["EA (kcal/kg FFM)"] = ((edited_df["Intake (kcal)"] - edited_df["Training Cals"]) / ffm_kg).round(1)

        st.dataframe(edited_df, use_container_width=True)

        tot_verbrauch = edited_df["Verbrauch (TDEE)"].sum()
        tot_intake = edited_df["Intake (kcal)"].sum()
        tot_bilanz = edited_df["Bilanz"].sum()
        avg_ea = edited_df["EA (kcal/kg FFM)"].mean()

        col_w1, col_w2, col_w3, col_w4 = st.columns(4)
        col_w1.metric("Wochen-Verbrauch", f"{tot_verbrauch} kcal")
        col_w2.metric("Wochen-Intake", f"{tot_intake} kcal")
        col_w3.metric("Wochen-Bilanz", f"{tot_bilanz} kcal")
        col_w4.metric("Ø Energy Availability", f"{round(avg_ea, 1)} kcal/kg")

        st.divider()

        # ==========================================
        # --- CLAUDE KI-COACH CHAT ---
        # ==========================================
        st.subheader("💬 Claude AI Performance & Nutrition Coach")
        st.markdown("Frag Claude zu deinen Live-Werten, Wochenbilanzen oder Intervall-Planungen.")

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
                            
                            system_context = f"""
Du bist der persönliche Ausdauercoach (Rennrad und Marathon) für Manuel Steiner.

### COACHING- UND KOMMUNIKATIONSSTIL
* Biete eine wissenschaftlich fundierte, evidenzbasierte Begründung anhand der Trainingsphysiologie.
* Objektive, rationale Antworten, keine unbegründete Zustimmung. Korrigiere fachlich nicht sinnvolle Einschätzungen direkt.
* Klares, natürliches Deutsch. Unnötige englische Begriffe vermeiden, wenn es deutsche Fachbegriffe gibt.
* Gedankenstriche NIEMALS als Ersatz für Kommata oder Satzzeichen verwenden.
* Bei Wochenplänen den genauen Inhalt der Workouts angeben (Intervallzeiten inkl. exakter Wattzahlen, HF-Bereiche, Pace beim Laufen). Keine Verteilung von Spannen/Ranges, sondern klare Einzelwerte.
* Bevorzuge einen periodisierten Trainingsansatz (ca. jede 4. Woche eine Entlastungswoche).
* Datums-, Wochentags- und Restzeit-Berechnungen (z. B. Tage bis zu einem Wettkampf) immer sorgfältig prüfen.

### ERNÄHRUNGSVORGABEN
* Kochvorschläge sind konsequent VEGETARISCH oder VEGAN (keine Fleischgerichte vorschlagen, auch nicht als Beilagenprotein).
* Mengenangaben bei Ernährung grundsätzlich als Rohgewicht.
* Bei geposteten Mahlzeiten: Automatische Analyse von Kalorien, Makros, Mikros (soweit sinnvoll), Proteinversorgung, KH-Versorgung, Fueling-Qualität, Passung zum Training, Timing und Verbesserungsvorschlägen.
* Energy Availability (EA = (Intake − Training) / FFM) muss über 30 kcal/kg Magermasse bleiben. Maximales tägliches Defizit ca. 300 kcal.
* Proteinziel: 145–155 g/Tag (~2,0–2,1 g/kg).

### ATHLETENPROFIL & BENCHMARKS
* Name: Manuel Steiner, Enterprise Architect bei SAP in München, 1,84 m, ~73 kg.
* Rennrad: FTP 319 W (Intervals.icu), 5-Minuten-Leistung 391 W, Schwellen-HF 169 bpm.
* HF-Zonen Rad: Z1 <135, Z2 132-142, Z3 143-154, Sweet Spot 155-162, Schwelle 163-170, VO2max >170 bpm.
* Laufen: Schwellenpace 3:42 min/km, Schwellen-HF 172 bpm.
* Ziele: Marathon unter 2:45 h (Berlin Marathon), UCI Gran Fondo Top 25% (Qualifikation World Championships).

### HEUTIGE LIVE-DATEN UND WOCHENÜBERSICHT
* Gewicht: {weight_kg} kg, Magermasse (FFM): {round(ffm_kg, 1)} kg, Grundumsatz (BMR): {int(bmr)} kcal.
* Heutige Schritte (NEAT): {step_calories} kcal ({steps} Schritte).
* Heutiger TDEE-Verbrauch: {total_today_output} kcal | Gegessen: {consumed_today} kcal.
* Heutige Bilanz: {net_balance} kcal | EA: {round(energy_availability, 1)} kcal/kg FFM.
* Geloggte Mahlzeiten heute: {st.session_state.logged_meals}
* Wochen-Tabelle (Intervals & Intake):
{edited_df.to_string()}
"""

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
