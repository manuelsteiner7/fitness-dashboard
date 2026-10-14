from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

# =====================================================================
# KONSTANTEN
# =====================================================================
TZ = ZoneInfo("Europe/Berlin")
BASE_URL = "https://intervals.icu/api/v1"
TIMEOUT = 20

BIRTHDATE = date(1995, 4, 20)
HEIGHT_CM = 184
FTP = 319
THRESHOLD_PACE_MIN_KM = 3 + 42 / 60
GRAN_FONDO = date(2026, 10, 18)

TEF = 0.08                      # thermischer Effekt der Nahrung, Anteil der Aufnahme
RUN_KCAL_PER_KG_KM = 1.0        # Netto-Laufkosten
KCAL_PER_STEP_PER_KG = 0.000375  # 0,5 kcal/kg/km bei ca. 1.333 Schritten pro km
STEPS_PER_RUN_KM = 1050         # Schritte, die beim Laufen schon im Lauf-Verbrauch stecken
DEFICIT_CAP = 500

RIDE_TYPES = {"Ride", "VirtualRide", "GravelRide", "MountainBikeRide"}
RUN_TYPES = {"Run", "TrailRun", "VirtualRun"}
WALK_TYPES = {"Walk", "Hike"}
EVENT_CATEGORIES = {"WORKOUT", "RACE_A", "RACE_B", "RACE_C"}

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

COACH_PROFILE = """Du bist der persönliche Ausdauercoach von Manuel Steiner (31 Jahre, 1,84 m, München, Enterprise Architect bei SAP), Schwerpunkt Marathon und Rennrad. Du begleitest Trainingsplanung, Ernährung und Regeneration langfristig wie ein erfahrener Coach und beantwortest nicht nur Einzelfragen.

LEISTUNGSDATEN
Laufen: Schwellenpace 3:42 min/km, Schwellenherzfrequenz 172 bpm.
Rad: FTP 319 W (Zeitfahren 14.06.2026), 5-Minuten-Leistung 391 W (18.06.2026), Schwellenherzfrequenz 169 bpm. Räder: Specialized Tarmac SL7 Pro mit Powermeter, Canyon Grail AL7 ohne Powermeter.
Herzfrequenzbereiche Rad: Z1 unter 135, Z2 (GA1/FATmax) 132 bis 142, Z3 (Tempo) 143 bis 154, Sweet Spot 155 bis 162, Schwelle 163 bis 170, VO2max über 170 bpm.
Empfehlungen immer mit Watt und Herzfrequenz (Rad) bzw. Pace und Herzfrequenz (Laufen) gemeinsam. Physiologische Bereiche sind wichtiger als starre Prozentwerte.

ZIELE
Berlin Marathon am 27.09.2026 (bereits vorbei). UCI Gran Fondo am 18.10.2026: 132 km, 2.275 Höhenmeter, Ziel Top 25 Prozent und Qualifikation für die UCI Weltmeisterschaften.
Langfristig: Marathon unter 2:45 Stunden, FTP steigern, VO2max steigern, Ermüdungsresistenz, Leistungsfähigkeit für 100 bis 200 km mit über 2.000 Höhenmetern, gesund und verletzungsfrei bleiben, Körpergewicht kontrolliert senken ohne Qualitätsverlust.

TRAININGSPHILOSOPHIE
Plane wie ein professioneller Ausdauercoach. Jede Einheit hat einen klaren physiologischen Zweck. Langfristiger Aufbau vor kurzfristigem Erfolg. Qualität vor Umfang. Wenn Manuel zu viel trainieren will, bremse ihn, wenn zu wenig, motiviere ihn. Denke mehrere Tage und Wochen voraus. Periodisiert, ungefähr jede vierte Woche eine Entlastungswoche. Wenn eine Einheit nicht sinnvoll ist, erkläre warum.
Wenn du Wochen planst, schreibe den genauen Inhalt jeder Einheit: Intervallzeiten inklusive Wattzahlen, Herzfrequenzbereiche, Pace beim Laufen. Ranges so klein wie möglich, bevorzugt klare Einzelwerte.
Vom 24.10.2026 bis 09.11.2026 ist Manuel auf Reise (Seoul und Hongkong) und trainiert frei und ungeplant. Für diesen Zeitraum keine Trainingspläne, Phasen oder gezielte Leistungssteuerung, außer er verlangt es ausdrücklich.

ERNÄHRUNG
Ziel ist aktuell Körperfettreduktion bei ausreichender Energie für intensive Einheiten. Das Defizit überschreitet nie 500 kcal. Energy Availability (EA) = (Aufnahme minus Trainingsverbrauch) / fettfreie Masse (ca. 62 kg). Unter 30 kcal/kg FFM besteht ein relevantes Risiko, optimal sind 40 bis 45. Manuel will meist um 30 liegen. Weise auf hohe Defizite der Vortage hin.
Kochvorschläge strikt vegetarisch, vegane Vorschläge willkommen, keine Fleischgerichte, auch nicht als Beilage. Mengen als Rohgewicht. Auswärts und in der Kantine isst er auch Fleisch.
Bei geposteten Mahlzeiten analysiere automatisch Kalorien, Makros, sinnvoll schätzbare Mikronährstoffe, Protein, Kohlenhydrate, Fueling-Qualität, Passung zum Training, Timing und Verbesserungen.
Referenzen: Crunch-Müsli je 100 g: 364 kcal, 6 g Fett, 64 g Kohlenhydrate (22 g Zucker), 9,5 g Eiweiß. HSN Soja-Proteinpulver je 100 g: 389 kcal, 1,8 g Fett, 1,4 g Kohlenhydrate, 92 g Eiweiß. Kantinenpizza ca. 620 kcal, 83 g Kohlenhydrate, 26 g Eiweiß, 18 g Fett.
Alltag: 6.000 bis 8.000 Schritte, sofern nicht anders angegeben.

ARBEITSWEISE MIT DEM DASHBOARD
Alle Zahlen im Abschnitt DASHBOARD-DATEN (Verbrauch, Bilanz, EA, Ziele, Makros) wurden von der App berechnet. Übernimm sie und rechne sie nicht neu. Wenn Informationen fehlen, frage gezielt nach. Arbeite evidenzbasiert, begründe kurz mit Trainingsphysiologie, sei objektiv, widersprich fachlich nicht sinnvollen Einschätzungen und vermeide unbegründete Zustimmung. Sprich klare Empfehlungen aus und erkläre Zielkonflikte. Schreibe klares, natürliches Deutsch, nutze deutsche Fachbegriffe, wo es etablierte gibt, und verwende Gedankenstriche nie als Ersatz für Kommata oder Satzzeichen. Datums-, Wochentags- und Restzeitangaben sorgfältig prüfen und die im Kontext genannten Daten verwenden."""

st.set_page_config(page_title="Performance & Nutrition Dashboard", page_icon="⚡", layout="wide")


# =====================================================================
# HILFSFUNKTIONEN
# =====================================================================
def secret(name, default=""):
    try:
        return st.secrets[name]
    except Exception:
        return default


def de_date(d):
    return f"{WEEKDAYS[d.weekday()]}, {d.strftime('%d.%m.%Y')}"


def calc_age(today):
    return today.year - BIRTHDATE.year - ((today.month, today.day) < (BIRTHDATE.month, BIRTHDATE.day))


@st.cache_data(ttl=300, show_spinner=False)
def api_get(path, key, params):
    try:
        r = requests.get(f"{BASE_URL}{path}", auth=("API_KEY", key), params=dict(params), timeout=TIMEOUT)
        if r.status_code == 200:
            return 200, r.json()
        return r.status_code, None
    except requests.RequestException:
        return 0, None


def day_of(item):
    return (item.get("start_date_local") or "")[:10]


# =====================================================================
# ENERGIEMODELL
# =====================================================================
def act_kcal(a, p):
    """Netto-Trainingsverbrauch (ohne Grundumsatz) einer Aktivität in kcal.
    Rückgabe: (kcal, Methode, Laufkilometer)"""
    t = a.get("type") or ""
    hours = (a.get("moving_time") or a.get("elapsed_time") or 0) / 3600
    if t in WALK_TYPES:
        return 0.0, "über Schritte erfasst", 0.0

    gear = a.get("gear")
    gear_name = gear.get("name", "") if isinstance(gear, dict) else str(gear or "")
    haystack = f"{gear_name} {a.get('name') or ''}".lower()
    kw = (p["nopower"] or "").strip().lower()
    has_power = not (kw and kw in haystack)

    joules = a.get("icu_joules")
    if t in RIDE_TYPES and joules and has_power:
        return joules / 1000.0, "Powermeter (kJ gleich kcal)", 0.0
    if t in RUN_TYPES and a.get("distance"):
        km = a["distance"] / 1000.0
        return p["weight"] * km * RUN_KCAL_PER_KG_KM, "Distanz mal Gewicht", km
    cal = a.get("calories")
    if cal:
        return max(cal - p["bmr"] / 24 * hours, 0.0), "Garmin abzüglich Grundumsatz", 0.0
    if joules:
        return joules / 1000.0, "kJ", 0.0
    return 0.0, "keine Daten", 0.0


def day_model(ds, acts, wd, p):
    ex, run_km, details = 0.0, 0.0, []
    for a in acts:
        k, how, km = act_kcal(a, p)
        ex += k
        run_km += km
        details.append(f"{a.get('name') or 'Training'} ({a.get('type') or '?'}): {int(k)} kcal, {how}")

    steps = wd.get("steps") or 0
    steps_src = "Garmin"
    if not steps:
        steps, steps_src = p["default_steps"], "Annahme"
    if ds == str(p["today"]) and steps < p["default_steps"]:
        steps, steps_src = p["default_steps"], "Annahme (Tag läuft noch)"
    steps_eff = max(steps - run_km * STEPS_PER_RUN_KM, 0)
    neat = steps_eff * KCAL_PER_STEP_PER_KG * p["weight"]
    base = (p["bmr"] + neat) * p["corr"]

    intake = wd.get("kcalConsumed") or 0
    tdee = base + ex + TEF * intake
    has_intake = intake > 0
    return {
        "ds": ds, "ex": ex, "steps": int(steps), "steps_src": steps_src, "neat": neat, "base": base,
        "intake": intake, "tdee": tdee, "details": details,
        "balance": (intake - tdee) if has_intake else None,
        "ea": ((intake - ex) / p["ffm"]) if has_intake else None,
        "carbs": wd.get("carbohydrates") or 0, "protein": wd.get("protein") or 0, "fat": wd.get("fatTotal") or 0,
    }


def est_event_kcal(ev, p):
    t = ev.get("type") or ""
    load = ev.get("icu_training_load") or 0
    secs = ev.get("moving_time") or 0
    if t in RUN_TYPES:
        if load:
            return load * p["weight"] * (60 / THRESHOLD_PACE_MIN_KM) / 100 * RUN_KCAL_PER_KG_KM
        return p["weight"] * 12 * secs / 3600
    if t in RIDE_TYPES:
        if load:
            return load * FTP * 0.036 * 0.92
        return FTP * 0.65 * 3.6 * secs / 3600
    return load * 8.0


def carb_floor_gkg(ex):
    if ex < 300:
        return 2.5
    if ex < 800:
        return 4.5
    if ex < 1400:
        return 6.0
    return 7.5


def plan_day(ex_est, p, deficit=None):
    deficit = p["deficit"] if deficit is None else deficit
    neat = p["default_steps"] * KCAL_PER_STEP_PER_KG * p["weight"]
    base = (p["bmr"] + neat) * p["corr"]
    tdee = (base + ex_est) / (1 - TEF)
    floor = ex_est + p["ea_min"] * p["ffm"]
    wanted = tdee - deficit
    target = max(wanted, floor)
    protein = p["weight"] * p["protein_gkg"]
    fat = p["weight"] * p["fat_gkg"]
    carbs = max((target - 4 * protein - 9 * fat) / 4, 0)
    return {
        "ex": ex_est, "tdee": tdee, "target": target, "limited": floor > wanted,
        "eff_deficit": tdee - target, "protein": protein, "fat": fat, "carbs": carbs,
        "carbs_gkg": carbs / p["weight"], "carb_floor": carb_floor_gkg(ex_est),
        "ea": (target - ex_est) / p["ffm"],
    }


def fueling(ev, p):
    t = ev.get("type") or ""
    secs = ev.get("moving_time") or 0
    h = secs / 3600
    load = ev.get("icu_training_load") or 0
    if_ = (load / (h * 100)) ** 0.5 if (h > 0 and load > 0) else 0.0
    if h * 60 < 60:
        g = 30 if if_ >= 0.85 else 0
    elif h <= 2.5:
        g = 40 if if_ < 0.70 else 60
    else:
        g = 60 if if_ < 0.70 else 90
    if t in RUN_TYPES:
        g = min(g, 75)
    return {
        "if": if_, "g_per_h": g, "total_g": int(round(g * h)),
        "fluid_ml": int(600 * h) if h >= 0.75 else 0,
        "sodium_mg": int(500 * h) if h >= 1 else 0,
        "pre_g": int(round(1.5 * p["weight"])) if h >= 1.5 else 0,
    }


def zone_summary(acts, key, only_types=None):
    tot = defaultdict(float)
    for a in acts:
        if only_types and (a.get("type") not in only_types):
            continue
        z = a.get(key)
        if not isinstance(z, list):
            continue
        for i, item in enumerate(z):
            if isinstance(item, dict) and "secs" in item:
                tot[str(item.get("id", f"Z{i+1}"))] += item["secs"] or 0
            elif isinstance(item, (int, float)):
                tot[f"Z{i+1}"] += item
    s = sum(tot.values())
    if not s:
        return "keine Daten"
    return ", ".join(f"{k} {v / s * 100:.0f}%" for k, v in tot.items())


def weekly_summary(acts):
    weeks = {}
    for a in acts:
        ds = day_of(a)
        if not ds:
            continue
        iso = date.fromisoformat(ds).isocalendar()
        w = weeks.setdefault((iso[0], iso[1]), {"h": 0.0, "tss": 0.0, "ride": 0.0, "run": 0.0, "km": 0.0})
        h = (a.get("moving_time") or 0) / 3600
        w["h"] += h
        w["tss"] += a.get("icu_training_load") or 0
        if a.get("type") in RIDE_TYPES:
            w["ride"] += h
        if a.get("type") in RUN_TYPES:
            w["run"] += h
            w["km"] += (a.get("distance") or 0) / 1000
    return [
        f"KW {k[1]}: {v['h']:.1f} h gesamt, TSS {v['tss']:.0f}, Rad {v['ride']:.1f} h, Lauf {v['run']:.1f} h ({v['km']:.0f} km)"
        for k, v in sorted(weeks.items())
    ]


def activity_line(a):
    parts = [day_of(a), a.get("type") or "?", f"'{a.get('name') or ''}'", f"{int((a.get('moving_time') or 0) / 60)} min"]
    if a.get("distance"):
        parts.append(f"{a['distance'] / 1000:.1f} km")
    if a.get("icu_average_watts"):
        parts.append(f"Ø {int(a['icu_average_watts'])} W")
    if a.get("icu_joules"):
        parts.append(f"{int(a['icu_joules'] / 1000)} kJ")
    if a.get("average_heartrate"):
        parts.append(f"Ø HF {int(a['average_heartrate'])}")
    if a.get("icu_training_load"):
        parts.append(f"TSS {int(a['icu_training_load'])}")
    return ", ".join(parts)


# =====================================================================
# SIDEBAR: ZUGANG UND PARAMETER
# =====================================================================
st.title("⚡ Performance & Nutrition Dashboard")
today = datetime.now(TZ).date()
st.caption(f"{de_date(today)} · Daten aus Intervals.icu · Rechenlogik in Python, Claude erklärt und berät")

athlete_id = secret("INTERVALS_ATHLETE_ID")
api_key = secret("INTERVALS_API_KEY")
claude_key = secret("ANTHROPIC_API_KEY")
claude_model = secret("CLAUDE_MODEL", "claude-sonnet-5-5")

st.sidebar.header("🔑 Zugang")
with st.sidebar.expander("Zugangsdaten", expanded=not (athlete_id and api_key)):
    athlete_id = st.text_input("Intervals Athlete ID", value=athlete_id)
    api_key = st.text_input("Intervals API Key", value=api_key, type="password")
    claude_key = st.text_input("Anthropic API Key", value=claude_key, type="password")
    claude_model = st.text_input("Claude Modell", value=claude_model)

st.sidebar.header("👤 Körper und Ziele")
weight_fallback = st.sidebar.number_input("Gewicht, falls nicht in Intervals.icu (kg)", value=70.5, step=0.1)
body_fat = st.sidebar.number_input("Körperfettanteil (%)", min_value=5.0, max_value=30.0, value=11.4, step=0.1)
deficit_goal = st.sidebar.number_input("Ziel-Defizit (kcal/Tag)", min_value=0, max_value=DEFICIT_CAP, value=400, step=50)
ea_min = st.sidebar.slider("EA-Untergrenze (kcal/kg FFM)", min_value=25.0, max_value=45.0, value=30.0, step=0.5)
protein_gkg = st.sidebar.number_input("Protein (g/kg)", min_value=1.4, max_value=2.6, value=2.0, step=0.1)
fat_gkg = st.sidebar.number_input("Fett (g/kg, Minimum)", min_value=0.7, max_value=1.6, value=1.0, step=0.1)
default_steps = st.sidebar.number_input("Standard-Schritte ohne Garmin-Daten", min_value=2000, max_value=25000, value=7000, step=500)
corr = st.sidebar.slider("Korrekturfaktor Grundverbrauch", min_value=0.85, max_value=1.15, value=1.00, step=0.01,
                         help="Nach 2 bis 3 Wochen mit Gewichtstrend und Intake kalibrieren.")
nopower_kw = st.sidebar.text_input("Rad ohne Powermeter (Stichwort im Namen/Rad)", value="Grail")

if not athlete_id or not api_key:
    st.warning("Bitte Intervals.icu Athlete ID und API Key in der Sidebar oder in den Streamlit Secrets hinterlegen.")
    st.stop()

# =====================================================================
# DATEN LADEN
# =====================================================================
s_w, wellness = api_get(f"/athlete/{athlete_id}/wellness", api_key,
                        (("oldest", str(today - timedelta(days=21))), ("newest", str(today))))
s_a, activities = api_get(f"/athlete/{athlete_id}/activities", api_key,
                          (("oldest", str(today - timedelta(days=21))), ("newest", str(today))))
s_e, events = api_get(f"/athlete/{athlete_id}/events", api_key,
                      (("oldest", str(today)), ("newest", str(today + timedelta(days=7)))))

if s_w != 200 or s_a != 200:
    st.error(f"Intervals.icu Abruf fehlgeschlagen (Wellness: {s_w}, Aktivitäten: {s_a}). Bitte ID und API Key prüfen.")
    st.stop()
if s_e != 200:
    st.warning(f"Geplante Workouts konnten nicht geladen werden (Status {s_e}).")
wellness, activities, events = wellness or [], activities or [], events or []
events = [e for e in events if (e.get("category") or "WORKOUT") in EVENT_CATEGORIES]

wellness_by_day = {str(w.get("id")): w for w in wellness}
acts_by_day, events_by_day = defaultdict(list), defaultdict(list)
for a in activities:
    acts_by_day[day_of(a)].append(a)
for e in events:
    events_by_day[day_of(e)].append(e)

weight = weight_fallback
for w in sorted(wellness, key=lambda x: str(x.get("id"))):
    if w.get("weight"):
        weight = float(w["weight"])
ffm = weight * (1 - body_fat / 100)
age = calc_age(today)
bmr = 10 * weight + 6.25 * HEIGHT_CM - 5 * age + 5

p = dict(weight=weight, bmr=bmr, ffm=ffm, corr=corr, deficit=deficit_goal, ea_min=ea_min,
         protein_gkg=protein_gkg, fat_gkg=fat_gkg, default_steps=default_steps, nopower=nopower_kw, today=today)

st.sidebar.caption(f"Gewicht {weight:.1f} kg · FFM {ffm:.1f} kg · Grundumsatz {int(bmr)} kcal · Alter {age}")

# =====================================================================
# SIDEBAR: ANSTEHENDE WORKOUTS MIT FUELING
# =====================================================================
st.sidebar.divider()
st.sidebar.header("📅 Anstehende Workouts")
upcoming = [e for e in events if day_of(e) >= str(today)]
if upcoming:
    options = {f"{day_of(e)} · {e.get('name') or 'Training'}": e for e in upcoming}
    ev = options[st.sidebar.selectbox("Workout", list(options.keys()))]
    f = fueling(ev, p)
    mins = int((ev.get("moving_time") or 0) / 60)
    with st.sidebar.expander(f"Details: {ev.get('name') or 'Training'}", expanded=True):
        st.markdown(f"**Datum:** {day_of(ev)} · **Typ:** {ev.get('type') or '?'}")
        st.markdown(f"**Dauer:** {mins} min · **TSS:** {int(ev.get('icu_training_load') or 0)} · **IF:** {f['if']:.2f}")
        st.markdown(f"**Geschätzter Verbrauch:** {int(est_event_kcal(ev, p))} kcal")
        if ev.get("description"):
            st.markdown(ev["description"])
        st.markdown("**Fueling**")
        st.markdown(f"- Während: **{f['g_per_h']} g Kohlenhydrate pro Stunde** (gesamt {f['total_g']} g)")
        if f["fluid_ml"]:
            st.markdown(f"- Flüssigkeit: {f['fluid_ml']} ml, Natrium {f['sodium_mg']} mg gesamt")
        if f["pre_g"]:
            st.markdown(f"- Vorher (ca. 3 h): {f['pre_g']} g Kohlenhydrate")
else:
    st.sidebar.info("Keine anstehenden Workouts im Kalender.")

# =====================================================================
# ERNÄHRUNG ERFASSEN
# =====================================================================
st.subheader("🍽️ Ernährung erfassen")
sel = st.date_input("Tag", value=today, min_value=today - timedelta(days=7), max_value=today)
wd_sel = wellness_by_day.get(str(sel), {})

with st.form("intake_form"):
    c1, c2, c3, c4 = st.columns(4)
    in_kcal = c1.number_input("Kalorien (kcal)", min_value=0, max_value=8000, step=50,
                              value=int(wd_sel.get("kcalConsumed") or 0), key=f"kcal_{sel}")
    in_carbs = c2.number_input("Kohlenhydrate (g)", min_value=0, max_value=1200, step=5,
                               value=int(wd_sel.get("carbohydrates") or 0), key=f"carb_{sel}")
    in_prot = c3.number_input("Protein (g)", min_value=0, max_value=400, step=5,
                              value=int(wd_sel.get("protein") or 0), key=f"prot_{sel}")
    in_fat = c4.number_input("Fett (g)", min_value=0, max_value=300, step=5,
                             value=int(wd_sel.get("fatTotal") or 0), key=f"fat_{sel}")
    saved = st.form_submit_button("In Intervals.icu speichern")

if saved:
    try:
        r = requests.put(f"{BASE_URL}/athlete/{athlete_id}/wellness/{sel}", auth=("API_KEY", api_key), timeout=TIMEOUT,
                         json={"kcalConsumed": int(in_kcal), "carbohydrates": float(in_carbs),
                               "protein": float(in_prot), "fatTotal": float(in_fat)})
        if r.status_code == 200:
            api_get.clear()
            st.rerun()
        else:
            st.error(f"Speichern fehlgeschlagen (Status {r.status_code}): {r.text[:200]}")
    except requests.RequestException as exc:
        st.error(f"Speichern fehlgeschlagen: {exc}")

with st.expander("Rohdaten Wellness für diesen Tag (zur Prüfung der Feldnamen)"):
    st.json(wd_sel if wd_sel else {"hinweis": "kein Eintrag"})

# =====================================================================
# MODELLE: HEUTE, VERLAUF, PLAN
# =====================================================================
today_model = day_model(str(today), acts_by_day.get(str(today), []), wellness_by_day.get(str(today), {}), p)
sel_model = day_model(str(sel), acts_by_day.get(str(sel), []), wd_sel, p)

hist = []
for i in range(1, 8):
    d = today - timedelta(days=i)
    hist.append(day_model(str(d), acts_by_day.get(str(d), []), wellness_by_day.get(str(d), {}), p))
recent = [h for h in hist[:3] if h["intake"] > 0]
avg_balance = sum(h["balance"] for h in recent) / len(recent) if recent else None
flag_recover = len(recent) >= 2 and avg_balance < -DEFICIT_CAP
low_ea_days = sum(1 for h in recent if h["ea"] < 30)

# =====================================================================
# HERO: TAGESBILANZ
# =====================================================================
st.divider()
st.subheader(f"🎯 Bilanz {de_date(sel)}")
m = sel_model
if sel == today:
    st.caption("Der laufende Tag ist vorläufig: Schritte werden mit mindestens dem Standardwert angesetzt.")

h1, h2, h3, h4 = st.columns(4)
h1.metric("Gesamtverbrauch", f"{int(m['tdee'])} kcal",
          delta=f"Grund {int(m['base'])} + Training {int(m['ex'])}" + (f" + TEF {int(TEF * m['intake'])}" if m["intake"] else ""),
          delta_color="off")
h2.metric("Aufnahme", f"{int(m['intake'])} kcal" if m["intake"] else "nicht erfasst")
if m["balance"] is not None:
    h3.metric("Bilanz", f"{int(m['balance']):+d} kcal", delta="Defizit" if m["balance"] < 0 else "Überschuss", delta_color="off")
    ea = m["ea"]
    state = "🟢 im Ziel" if ea >= ea_min else ("🟡 knapp darunter" if ea >= ea_min - 3 else "🔴 zu niedrig")
    h4.metric("Energy Availability", f"{ea:.1f} kcal/kg FFM", delta=f"{state} (Ziel ab {ea_min:.0f})", delta_color="off")
else:
    h3.metric("Bilanz", "offen")
    h4.metric("Energy Availability", "offen")

with st.expander("Aufschlüsselung"):
    st.markdown(f"- Grundumsatz mal Korrekturfaktor: **{int(bmr * corr)} kcal**")
    st.markdown(f"- Alltagsbewegung: **{int(m['neat'] * corr)} kcal** ({m['steps']} Schritte, Quelle: {m['steps_src']})")
    if m["details"]:
        st.markdown("- Einheiten:")
        for line in m["details"]:
            st.markdown(f"  - {line}")
    else:
        st.markdown("- Keine Einheiten erfasst (Ruhetag oder noch nicht synchronisiert).")

# Warnungen zum mehrtägigen Defizit
if flag_recover:
    st.warning(f"Die letzten {len(recent)} Tage lagen im Schnitt bei {int(avg_balance)} kcal Bilanz, über deiner Grenze von "
               f"{DEFICIT_CAP} kcal. Heute und morgen plane ich deshalb Erhaltung statt Defizit.")
elif low_ea_days >= 2:
    st.warning(f"An {low_ea_days} der letzten {len(recent)} erfassten Tage lag die EA unter 30 kcal/kg FFM. "
               "Wiederholt führt das zu schlechterer Regeneration und Leistungsfähigkeit.")

# =====================================================================
# ZIELE FÜR 4 TAGE
# =====================================================================
st.divider()
st.subheader("📋 Ziele für die nächsten 4 Tage")
cols = st.columns(4)
plans = []
for i in range(4):
    d = today + timedelta(days=i)
    ds = str(d)
    evs = events_by_day.get(ds, [])
    planned_ex = sum(est_event_kcal(e, p) for e in evs)
    ex_est = max(today_model["ex"], planned_ex) if i == 0 else planned_ex
    deficit_day = 0 if (flag_recover and i <= 1) else p["deficit"]
    pl = plan_day(ex_est, p, deficit_day)
    plans.append((d, evs, pl))
    with cols[i]:
        st.markdown(f"### {'Heute' if i == 0 else d.strftime('%d.%m.')}")
        st.caption(("🗓️ " + ", ".join((e.get("name") or "Training") for e in evs)) if evs else "Ruhetag oder frei")
        st.metric("Ziel-Kalorien", f"{int(pl['target'])} kcal")
        st.markdown(
            f"- Kohlenhydrate: **{int(pl['carbs'])} g** ({pl['carbs_gkg']:.1f} g/kg)\n"
            f"- Protein: **{int(pl['protein'])} g**\n"
            f"- Fett: **{int(pl['fat'])} g**\n"
            f"- Training: **{int(pl['ex'])} kcal**\n"
            f"- EA: **{pl['ea']:.1f}** · Defizit: **{int(pl['eff_deficit'])} kcal**"
        )
        if pl["limited"]:
            st.caption("EA-Untergrenze begrenzt das Defizit.")
        if pl["carbs_gkg"] < pl["carb_floor"]:
            st.caption(f"⚠️ Kohlenhydrate unter dem Richtwert von {pl['carb_floor']} g/kg für diese Belastung.")

if sel == today:
    pl_today = plans[0][2]
    st.markdown("**Heute im Verlauf**")
    pc1, pc2, pc3, pc4 = st.columns(4)
    pc1.metric("Kalorien offen", f"{int(pl_today['target'] - m['intake'])} kcal" if m["intake"] else f"{int(pl_today['target'])} kcal")
    pc2.metric("Kohlenhydrate", f"{int(m['carbs'])} / {int(pl_today['carbs'])} g")
    pc3.metric("Protein", f"{int(m['protein'])} / {int(pl_today['protein'])} g")
    pc4.metric("Fett", f"{int(m['fat'])} / {int(pl_today['fat'])} g")

# =====================================================================
# VERLAUF 7 TAGE
# =====================================================================
st.divider()
st.subheader("📈 Letzte 7 Tage")
rows = []
for h in hist:
    rows.append({
        "Tag": h["ds"], "Training (kcal)": int(h["ex"]), "Schritte": h["steps"],
        "Aufnahme (kcal)": int(h["intake"]) if h["intake"] else None,
        "Verbrauch (kcal)": int(h["tdee"]),
        "Bilanz (kcal)": int(h["balance"]) if h["balance"] is not None else None,
        "EA": round(h["ea"], 1) if h["ea"] is not None else None,
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

with st.expander("Annahmen der Berechnung"):
    st.markdown(
        f"- Grundumsatz nach Mifflin St Jeor mit aktuellem Gewicht, Größe {HEIGHT_CM} cm und Alter {age}.\n"
        f"- Alltagsbewegung aus Garmin-Schritten (0,5 kcal/kg/km netto), Laufschritte abgezogen, damit nichts doppelt zählt.\n"
        f"- Rad mit Powermeter: kJ Arbeit entsprechen etwa kcal Netto-Verbrauch. Laufen: 1 kcal pro kg und km. "
        f"Sonstiges: Garmin-Kalorien abzüglich Grundumsatz der Dauer.\n"
        f"- Thermischer Effekt der Nahrung: {int(TEF * 100)} Prozent der Aufnahme.\n"
        f"- Geplante Einheiten: Rad ca. {FTP * 0.036 * 0.92:.1f} kcal pro TSS, Laufen ca. "
        f"{p['weight'] * (60 / THRESHOLD_PACE_MIN_KM) / 100:.1f} kcal pro TSS.\n"
        f"- Ziel-Kalorien: Verbrauch minus Defizit, mindestens Training plus EA-Untergrenze mal fettfreie Masse. "
        f"Protein und Fett fest, Kohlenhydrate aus dem Rest.\n"
        f"- Die Einheiten aus Intervals.icu sind Schätzungen. Mit dem Korrekturfaktor kannst du nach einigen Wochen "
        f"gegen den Gewichtstrend kalibrieren."
    )

# =====================================================================
# CLAUDE COACH
# =====================================================================
def build_context():
    days_to_gf = (GRAN_FONDO - today).days
    lines = [f"DASHBOARD-DATEN (von der App berechnet)",
             f"Heute: {de_date(today)}. Tage bis UCI Gran Fondo am {de_date(GRAN_FONDO)}: {days_to_gf}.",
             f"Gewicht {weight:.1f} kg, Körperfett {body_fat:.1f} %, FFM {ffm:.1f} kg, Grundumsatz {int(bmr)} kcal, "
             f"Ziel-Defizit {deficit_goal} kcal, EA-Untergrenze {ea_min:.0f}.",
             "", f"HEUTE ({de_date(today)}):",
             f"Training bisher {int(today_model['ex'])} kcal, Schritte {today_model['steps']}, "
             f"Aufnahme {int(today_model['intake'])} kcal, Kohlenhydrate {int(today_model['carbs'])} g, "
             f"Protein {int(today_model['protein'])} g, Fett {int(today_model['fat'])} g.",
             f"Verbrauch (vorläufig) {int(today_model['tdee'])} kcal."]
    if today_model["balance"] is not None:
        lines.append(f"Bilanz {int(today_model['balance'])} kcal, EA {today_model['ea']:.1f} kcal/kg FFM.")
    lines += ["", "ZIELE NÄCHSTE 4 TAGE:"]
    for d, evs, pl in plans:
        names = ", ".join((e.get("name") or "Training") for e in evs) or "keine Einheit"
        lines.append(f"{de_date(d)}: {names}. Training ca. {int(pl['ex'])} kcal, Ziel {int(pl['target'])} kcal, "
                     f"Kohlenhydrate {int(pl['carbs'])} g, Protein {int(pl['protein'])} g, Fett {int(pl['fat'])} g, "
                     f"EA {pl['ea']:.1f}, Defizit {int(pl['eff_deficit'])} kcal.")
    lines += ["", "LETZTE 7 TAGE (ohne heute):"]
    for h in hist:
        if h["intake"]:
            lines.append(f"{h['ds']}: Aufnahme {int(h['intake'])}, Verbrauch {int(h['tdee'])}, Bilanz {int(h['balance'])}, "
                         f"EA {h['ea']:.1f}, Training {int(h['ex'])} kcal")
        else:
            lines.append(f"{h['ds']}: Aufnahme nicht erfasst, Training {int(h['ex'])} kcal")
    if flag_recover:
        lines.append("HINWEIS: Mehrtägiges Defizit über der Grenze, Erhaltung für heute und morgen eingeplant.")
    lines += ["", "TRAININGSBELASTUNG LETZTE 21 TAGE:"] + weekly_summary(activities)
    lines.append("Leistungszonen Rad: " + zone_summary(activities, "icu_zone_times", RIDE_TYPES))
    lines.append("HF-Zonen gesamt: " + zone_summary(activities, "icu_hr_zone_times"))
    lines += ["", "EINHEITEN (neueste zuerst, max. 45):"]
    for a in sorted(activities, key=lambda x: x.get("start_date_local") or "", reverse=True)[:45]:
        lines.append(activity_line(a))
    lines += ["", "GEPLANTE WORKOUTS (nächste 7 Tage):"]
    if events:
        for e in events:
            desc = (e.get("description") or "").replace("\n", " ")[:400]
            lines.append(f"{day_of(e)}: {e.get('name') or 'Training'} ({e.get('type') or '?'}), "
                         f"{int((e.get('moving_time') or 0) / 60)} min, TSS {int(e.get('icu_training_load') or 0)}. {desc}")
    else:
        lines.append("keine")
    lines += ["", "Hinweis: Laps und Segmente sind in diesen Daten nicht enthalten."]
    return "\n".join(lines)


st.divider()
st.subheader("💬 Coach")

if not claude_key:
    st.info("Trage den Anthropic API Key ein, um den Coach zu aktivieren.")
else:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if st.button("Chat leeren"):
        st.session_state.messages = []
        st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Frage zu Training, Bilanz, Fueling oder Mahlzeiten ..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Coach analysiert ..."):
                try:
                    payload = {
                        "model": claude_model,
                        "max_tokens": 1500,
                        "system": [
                            {"type": "text", "text": COACH_PROFILE, "cache_control": {"type": "ephemeral"}},
                            {"type": "text", "text": build_context()},
                        ],
                        "messages": [{"role": m_["role"], "content": m_["content"]} for m_ in st.session_state.messages[-20:]],
                    }
                    r = requests.post("https://api.anthropic.com/v1/messages", timeout=90, json=payload,
                                      headers={"x-api-key": claude_key, "anthropic-version": "2023-06-01",
                                               "content-type": "application/json"})
                    data = r.json()
                    if r.status_code == 200:
                        reply = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
                    else:
                        reply = f"API-Fehler ({r.status_code}): {data.get('error', {}).get('message', str(data))}"
                except Exception as exc:
                    reply = f"Fehler: {exc}"
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
