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


# =========================
# PERIOD SCORE HELPERS
# =========================

def get_livescore_period_score(ev, sport):
    """livescore-ის ტაიმების ანგარიში სპორტის მიხედვით"""
    parts = []

    if sport == "hockey":
        for i in range(1, 4):
            t1 = ev.get(f"Tr1Pe{i}")
            t2 = ev.get(f"Tr2Pe{i}")
            if t1 is not None and t2 is not None:
                parts.append(f"{t1}:{t2}")

    elif sport == "basketball":
        for i in range(1, 5):
            t1 = ev.get(f"Tr1Q{i}")
            t2 = ev.get(f"Tr2Q{i}")
            if t1 is not None and t2 is not None:
                parts.append(f"{t1}:{t2}")

    elif sport == "tennis":
        for i in range(1, 6):
            t1 = ev.get(f"Tr1S{i}")
            t2 = ev.get(f"Tr2S{i}")
            if t1 is not None and t2 is not None:
                parts.append(f"{t1}:{t2}")

    if parts:
        return "[" + ", ".join(parts) + "]"
    return ""


def get_betcity_period_score(sc_add_ev):
    """betcity-ს sc_add_ev ველიდან ტაიმების ანგარიში"""
    if not sc_add_ev or not sc_add_ev.strip():
        return ""

    parts = [p.strip().replace(":", "-") for p in sc_add_ev.split(",") if p.strip()]
    # უკან ვაბრუნებთ : სიმბოლოთი
    parts = [p.replace("-", ":") for p in parts]

    if parts:
        return "[" + ", ".join(parts) + "]"
    return ""


# suffix_map betcity-სთვის
BETCITY_SUFFIX_MAPS = {
    "basketballBC": {
        " (3-х очк. попадания)": " (3 quliani)",
        " (2-х очк. попадания)": " (2 quliani)",
        " (подборы)": " (moxsna)",
        " (фолы)": " (foli)",
        " (заб. штрафные)": " (gat. jarimebi)",
        "(ж)": " (q)",
        "(шк.)": " (sk.)",
        "(3x3)": " (3/3)",
        "(3х3)": " (3/3)",
        "(шк)": " (sk)",
        "(сурд)": " (surd)",
        "(унив)": " (univ)",
        " (мол)": " (ax)",
        " (мол.)": " (ax)",
        " (Рез)": " (rez)",
        " (макк)": " (mak)",
    },
    "tennisBC": {
        " (геймы)": " (geim.)",
        " (пары)": " (wyv.)",
        " (дв. ошибки)": " (ormagi Secd.)",
        " (эйсы)": " (eisi)",
        " (srl)": " (srl)",
    },
    "handballBC": {
        " (мол)": " (ax)",
        " (ж)": " (q)",
        "(унив)": " (univ)",
        "(кол-во 2-х мин. уд.)": " (2wT gaZ. rao-ba)",
        "(7-метр. штр. бр.)": " (7-metr. saj. dar.)",
    },
    "rugbyBC": {
        " (ж)": " (q)",
    },
    "volleyballBC": {
        "(ж)": " (q)",
        "(люб)": " (moy)",
        "(4x4)": " (4/4)",
        "(4х4)": " (4/4)",
        "(микст)": " (mikst)",
        "(рез)": " (rez)",
        "(школ)": " (skol)",
        "(мол)": " (ax)",
        "(юноши)": " (iun)",
        "(воен)": " (samx)",
        "(унив)": " (univ)",
        "(кад)": " (kad)",
        "(мол. сб.)": " (ax. nak.)",
        "(ошибки на подачах)": " (Secdoma Cawodebaze)",
        "(эйсы)": " (eisi)",
        "(блоки)": " (bloki)",
        " (макк)": " (mak)",
        " (полиция)": " (policia)",
    },
}

PERIOD_SUFFIXES = {
    "basketballBC": [
        " (13)", " (14)", " (15)", " (16)", " (17)", " (18)", " (19)",
        " (20)", " (21)", " (22)", " (23)", " (24)", " (25)",
        " (40)", " (45)", " (50)", " (55)", " (45+)",
    ],
    "handballBC": [
        " (16)", " (17)", " (18)", " (19)", " (20)", " (21)", " (22)",
    ],
    "rugbyBC": [
        " (18)", " (19)", " (20)",
    ],
    "volleyballBC": [
        " (14)", " (15)", " (16)", " (17)", " (18)", " (19)", " (20)",
        " (21)", " (22)", " (23)",
    ],
}


def translate_betcity_name(name, source):
    db = SessionLocal()
    original = name.strip()
    lower = original.lower()
    suffix = ""

    period_list = PERIOD_SUFFIXES.get(source, [])
    for ps in period_list:
        if lower.endswith(ps.lower()):
            suffix = ps
            lower = lower[:-len(ps)].strip()
            break

    if not suffix:
        m = re.search(r"\((1[2-9]|2[0-3])\)$", lower)
        if m:
            suffix = " " + m.group(0)
            lower = lower[:m.start()].strip()

    sport_map = BETCITY_SUFFIX_MAPS.get(source, {})

    common_suffix_map = {
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

    combined_map = {**common_suffix_map, **sport_map}

    if not suffix:
        for k, v in combined_map.items():
            if lower.endswith(k.lower()):
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


def translate_tennis_betcity(name, source):
    if "/" in name:
        parts = name.split("/", 1)
        left = translate_betcity_name(parts[0].strip(), source)
        right = translate_betcity_name(parts[1].strip(), source)
        return left + " / " + right
    return translate_betcity_name(name, source)


def translate_tennis_livescore(name, source):
    if " / " in name:
        parts = name.split(" / ", 1)
        left = translate(parts[0].strip(), source)
        right = translate(parts[1].strip(), source)
        return left + " / " + right
    return translate(name, source)


def translate(name, source):
    db = SessionLocal()

    if source in ("betcity", "hockeyBC", "basketballBC", "handballBC", "rugbyBC", "volleyballBC"):
        db.close()
        return translate_betcity_name(name, source)

    if source == "tennisBC":
        db.close()
        return translate_tennis_betcity(name, source)

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
            t1_list = ev.get("T1", [{}])
            t2_list = ev.get("T2", [{}])

            if len(t1_list) >= 2:
                team1 = t1_list[0].get("Nm", "").strip() + " / " + t1_list[1].get("Nm", "").strip()
                team2 = t2_list[0].get("Nm", "").strip() + " / " + t2_list[1].get("Nm", "").strip()
            else:
                team1 = t1_list[0].get("Nm", "").strip()
                team2 = t2_list[0].get("Nm", "").strip()

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

            # ტაიმების ანგარიში
            period_score = get_livescore_period_score(ev, sport) if sport in ("hockey", "basketball", "tennis") else ""

            if sport == "hockey":
                clean1, suf1 = normalize_hockey_livescore(team1)
                clean2, suf2 = normalize_hockey_livescore(team2)
                t1 = translate(clean1, source_key)
                t2 = translate(clean2, source_key)
                if suf1:
                    t1 = t1 + " " + suf1
                if suf2:
                    t2 = t2 + " " + suf2
            elif sport == "tennis":
                t1 = translate_tennis_livescore(team1, source_key)
                t2 = translate_tennis_livescore(team2, source_key)
            else:
                t1 = translate(team1, source_key)
                t2 = translate(team2, source_key)

            matches.append({
                "league": league,
                "country": country,
                "minute": minute,
                "team1": t1,
                "score": score,
                "period_score": period_score,
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

                period_score = get_betcity_period_score(ev.get("sc_add_ev", ""))

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
                    "period_score": period_score,
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
        skip_keywords=["статистика", "кибербаскетбол"]
    )

def fetch_betcity_tennis():
    return fetch_betcity_sport(
        "теннис", "tennisBC", "Tennis.gif",
        skip_keywords=["статистика", "настольный теннис"]
    )

def fetch_betcity_handball():
    return fetch_betcity_sport(
        "гандбол", "handballBC", "Handball.gif",
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
