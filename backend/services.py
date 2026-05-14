import re
import requests
from db import SessionLocal
from models import Translation
from loader import livescore_flags, betcity_flags
from datetime import datetime

matches_cache = {
    "livescore": [],
    "livescore_hockey": [],
    "livescore_basketball": [],
    "livescore_tennis": [],
    "betcity": [],
    "betcity_hockey": [],
    "betcity_basketball": [],
    "betcity_tennis": [],
    "betcity_handball": [],
    "betcity_rugby": [],
    "betcity_volleyball": [],
}

def normalize_team_name(name):
    name = name.strip()
    lower = name.lower()

    prefix_map = {
        "fc": "",
        "cf": "",
        "fk": "",
        "kf": ""
    }

    suffix_map = {
        "u17": "(17)",
        "u18": "(18)",
        "u19": "(19)",
        "u20": "(20)",
        "u21": "(21)",
        "u22": "(22)",
        "u23": "(23)",
        "(a)": "(a)",
        "(w)": "(q)",
        "wfc": "(q)",
        "womens": "(q)",
        "women": "(q)",
        "ladies": "(q)",
        "reserves": "rezervi",
        "reserve": "rezervi",
        "w": "(q)",
        "fc": "",
        "cf": "",
        "fk": "",
        "kf": ""
    }

    prefix = ""
    suffixes = []

    # --- PREFIX ---
    parts = name.split(" ", 1)
    if len(parts) > 1:
        first = parts[0].lower()
        if first in prefix_map:
            prefix = prefix_map[first]
            name = parts[1].strip()

    # --- MULTIPLE SUFFIX ---
    while True:
        parts = name.rsplit(" ", 1)

        if len(parts) < 2:
            break

        last = parts[1].lower()

        if last in suffix_map:
            mapped = suffix_map[last]

            if mapped:
                suffixes.insert(0, mapped)

            name = parts[0].strip()
        else:
            break

    suffix = " ".join(suffixes) if suffixes else ""

    return name, prefix, suffix


def normalize_hockey_livescore(name):
    name = name.strip()
    lower = name.lower()

    suffix_map = {
        "u18": "(18)",
        "u19": "(19)",
        "u20": "(20)",
        "u23": "(23)",
        "(w)": "(q)",
        "3x3": "3X3",
        "womens": "(q)",
        "women": "(q)",
        "w": "(q)",
    }

    for p in ["hk ", "hc "]:
        if lower.startswith(p):
            name = name[len(p):].strip()
            lower = name.lower()
            break

    for s in [" hk", " hc"]:
        if lower.endswith(s):
            name = name[:-len(s)].strip()
            lower = name.lower()
            break

    suffix = ""

    while True:
        parts = name.rsplit(" ", 1)
        if len(parts) < 2:
            break
        last = parts[1].lower()
        if last in suffix_map:
            mapped = suffix_map[last]
            suffix = mapped + (" " + suffix if suffix else "")
            name = parts[0].strip()
            lower = name.lower()
        else:
            break

    if name.lower().endswith("(w)"):
        suffix = "(q)" + (" " + suffix if suffix else "")
        name = name[:-3].strip()

    return name.strip(), suffix


def get_today():
    return datetime.now().strftime("%Y%m%d")


def translate(name, source):
    db = SessionLocal()

    if source in ("betcity", "hockeyBC", "basketballBC", "tennisBC", "handballBC", "rugbyBC", "volleyballBC"):
        original = name.strip()
        lower = original.lower()
        suffix = ""

        m = re.search(r"\((1[2-9]|2[0-3])\)$", lower)
        if m:
            suffix = " " + m.group(0)
            lower = lower[:m.start()].strip()

        suffix_map = {
            " (мол)": " (ax)",
            " (юн)": " (iun)",
            " (олимп)": " (olimp)",
            " (жен)": " (qal)",
            " (ж)": " (q)",
            " (люб)": " (moy)",
            " (люб.)": " (moyv)",
            " (резерв)": " (rezerv)",
            " (унив)": " (univ)",
            " (рез)": " (rez)",
            " (3x3)": " (3/3)",
            " (3х3)": " (3/3)",
            " (4x4)": " (4/4)",
            " (4х4)": " (4/4)",
            " (5x5)": " (5/5)",
            " (5х5)": " (5/5)",
            " (6x6)": " (6/6)",
            " (6х6)": " (6/6)",
            " (7x7)": " (6/6)",
            " (7х7)": " (6/6)",
            " (мини-футбол)": " (mini-fexb.)",
            " угл": "(kuTx.) ",
            " жк": "(yv.) ",
            # hockey
            " (штр)": " (saj)",
            " (бр)": " (dart)",
            " (сб. кл.)": " (kl. nak.)",
            " (2x2)": " (2/2)",
            " (2х2)": " (2/2)",
            " (нов)": " (ax)",
            " (до 18)": " (18-mde)",
            " (до 22)": " (22-mde)",
            " (сб. МХЛ)": " (nakr.МХЛ)",
            " (BCHL)": " (BCHL)",
            " (WHL)": " (dhl)",
            " (EJHL)": " (aihl)",
            " (голы в бол.)": " (goli met.)",
            " (выиг. вбрасывания)": " (Cagd. mogeba)",
            " (блок. бр.)": " (dart. blok.)",
            " (сил. приёмы)": " (Zal. ileTi)",
            " (видеопросмотры)": " (video Cveneba)",
        }

        for k, v in suffix_map.items():
            if lower.endswith(k):
                suffix = v
                lower = lower[:-len(k)].strip()
                break

        if lower.startswith("фк "):
            lower = lower[3:].strip()

        if lower.endswith(" фк"):
            lower = lower[:-3].strip()

        result = db.query(Translation).filter(
            Translation.source_name == lower,
            Translation.source == source
        ).first()

        db.close()

        translated = result.georgian_name if result else lower

        if suffix:
            translated = translated + suffix

        return translated.strip()

    # --- LIVESCORE ---
    clean_name, prefix, suffix = normalize_team_name(name)

    clean_name = clean_name.strip().lower()

    result = db.query(Translation).filter(
        Translation.source_name == clean_name,
        Translation.source == source
    ).first()

    db.close()

    translated = result.georgian_name if result else clean_name

    if suffix:
        translated = translated + " " + suffix

    return translated.strip()


# =========================
# LIVESCORE — საერთო ფუნქცია
# =========================

def fetch_livescore_sport(sport, source_key, sport_icon):
    url = f"https://prod-public-api.livescore.com/v1/api/app/date/{sport}/{get_today()}/4?countryCode=GE&locale=en&MD=1"

    try:
        res = requests.get(url, timeout=10)
        data = res.json()
    except:
        return []

    matches = []

    for stage in data.get("Stages", []):
        league = stage.get("Snm", "")
        country = stage.get("Cnm") or ""
        flag = livescore_flags.get(country.strip()) or livescore_flags.get(country.strip().title())

        for ev in stage.get("Events", []):
            team1 = ev.get("T1", [{}])[0].get("Nm", "").strip()
            team2 = ev.get("T2", [{}])[0].get("Nm", "").strip()

            ft = ev.get("Eps", "")

            if ft != "NS":
                score = f"{ev.get('Tr1', 0)} - {ev.get('Tr2', 0)}"
                minute = ft
            else:
                score = "? - ?"
                esd = str(ev.get("Esd", ""))
                if esd:
                    t = esd[8:12]
                    minute = f"{t[:2]}:{t[2:]}"
                else:
                    minute = ""

            if re.match(r'^\d{2}:\d{2}$', minute):
                continue

            if sport == "hockey":
                clean1, suf1 = normalize_hockey_livescore(team1)
                clean2, suf2 = normalize_hockey_livescore(team2)
                t1 = translate(clean1, source_key)
                t2 = translate(clean2, source_key)
                if suf1:
                    t1 = t1 + " " + suf1
                if suf2:
                    t2 = t2 + " " + suf2
            else:
                t1 = translate(team1, source_key)
                t2 = translate(team2, source_key)

            matches.append({
                "league": league,
                "country": country,
                "minute": minute,
                "team1": t1,
                "score": score,
                "team2": t2,
                "flag": flag,
                "sport_icon": sport_icon,
                "source": "livescore"
            })

    return matches


def fetch_livescore():
    return fetch_livescore_sport("soccer", "livescore", "Soccer.gif")

def fetch_livescore_hockey():
    return fetch_livescore_sport("hockey", "hockey", "Hockey.gif")

def fetch_livescore_basketball():
    return fetch_livescore_sport("basketball", "basketball", "Basketball.gif")

def fetch_livescore_tennis():
    return fetch_livescore_sport("tennis", "tennis", "Tennis.gif")


# =========================
# BETCITY — საერთო ფუნქცია
# =========================

def fetch_betcity_sport(sport_keyword, source_key, sport_icon, skip_keywords=None):
    url = "https://ap.betcityru.com/api/v1/live/results?rev=3&ver=96&csn=f9xg7b"

    try:
        res = requests.get(url, timeout=10)
        data = res.json()
    except:
        return []

    matches = []
    skip_keywords = skip_keywords or []

    sports = data.get("reply", {}).get("sports", {})

    for sp in sports.values():
        sport_name = sp.get("name_sp", "").lower()

        if sport_keyword not in sport_name:
            continue

        for ch in sp.get("chmps", {}).values():
            league = ch.get("name_ch", "")

            if any(kw in league.lower() for kw in skip_keywords):
                continue

            country = ""
            flag = None
            for k, v in betcity_flags.items():
                if " " + k.lower() in league.lower():
                    flag = v
                    break

            for ev in ch.get("evts", {}).values():
                team1 = ev.get("name_ht", "").strip()
                team2 = ev.get("name_at", "").strip()

                score_raw = ev.get("sc_ev", "")
                score_clean = re.sub(r'^[А-Яа-яA-Za-z]+\s+', '', score_raw).strip()

                if ":" in score_clean:
                    s1, s2 = score_clean.split(":", 1)
                    score = f"{s1} - {s2}"
                else:
                    score = "? - ?"

                if ev.get("st_ev") == 2:
                    minute = "FT"
                else:
                    minute = ""

                matches.append({
                    "league": league,
                    "country": country,
                    "minute": minute,
                    "team1": translate(team1, source_key),
                    "score": score,
                    "team2": translate(team2, source_key),
                    "flag": flag,
                    "sport_icon": sport_icon,
                    "source": "betcity"
                })

    return matches


def fetch_betcity():
    return fetch_betcity_sport(
        "футбол", "betcity", "Soccer.gif",
        skip_keywords=["киберфутбол", "статистика", "австралийский футбол"]
    )

def fetch_betcity_hockey():
    return fetch_betcity_sport(
        "хоккей", "hockeyBC", "Hockey.gif",
        skip_keywords=["статистика", "киберхоккей"]
    )

def fetch_betcity_basketball():
    return fetch_betcity_sport(
        "баскетбол", "basketballBC", "Basketball.gif",
        skip_keywords=["статистика"]
    )

def fetch_betcity_tennis():
    return fetch_betcity_sport(
        "теннис", "tennisBC", "Tennis.gif",
        skip_keywords=["статистика"]
    )

def fetch_betcity_handball():
    return fetch_betcity_sport(
        "гандбол", "handballBC", "handball.gif",
        skip_keywords=["статистика"]
    )

def fetch_betcity_rugby():
    return fetch_betcity_sport(
        "регби", "rugbyBC", "Rugby.gif",
        skip_keywords=["статистика"]
    )

def fetch_betcity_volleyball():
    return fetch_betcity_sport(
        "волейбол", "volleyballBC", "Volleyball.gif",
        skip_keywords=["статистика"]
    )


# =========================
# UPDATE CACHE
# =========================

def update_matches():
    matches_cache["livescore"] = fetch_livescore()
    matches_cache["livescore_hockey"] = fetch_livescore_hockey()
    matches_cache["livescore_basketball"] = fetch_livescore_basketball()
    matches_cache["livescore_tennis"] = fetch_livescore_tennis()
    matches_cache["betcity"] = fetch_betcity()
    matches_cache["betcity_hockey"] = fetch_betcity_hockey()
    matches_cache["betcity_basketball"] = fetch_betcity_basketball()
    matches_cache["betcity_tennis"] = fetch_betcity_tennis()
    matches_cache["betcity_handball"] = fetch_betcity_handball()
    matches_cache["betcity_rugby"] = fetch_betcity_rugby()
    matches_cache["betcity_volleyball"] = fetch_betcity_volleyball()


def get_all_matches():
    all_matches = []
    all_matches.extend(matches_cache["livescore"])
    all_matches.extend(matches_cache["livescore_hockey"])
    all_matches.extend(matches_cache["livescore_basketball"])
    all_matches.extend(matches_cache["livescore_tennis"])
    all_matches.extend(matches_cache["betcity"])
    all_matches.extend(matches_cache["betcity_hockey"])
    all_matches.extend(matches_cache["betcity_basketball"])
    all_matches.extend(matches_cache["betcity_tennis"])
    all_matches.extend(matches_cache["betcity_handball"])
    all_matches.extend(matches_cache["betcity_rugby"])
    all_matches.extend(matches_cache["betcity_volleyball"])
    return all_matches
