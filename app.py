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
                            "model": "claude-haiku-4-5-20251001",
                            "max_tokens": 300,
                            "messages": [{"role": "user", "content": prompt_analysis}]
                        }
