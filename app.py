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
