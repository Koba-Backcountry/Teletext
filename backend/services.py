import re
import requests
from db import SessionLocal
from models import Translation
from loader import livescore_flags, betcity_flags
from datetime import datetime

matches_cache = {
    "livescore":            [],
    "livescore_hockey":     [],
    "livescore_basketball": [],
    "livescore_tennis":     [],
    "betcity":              [],
    "betcity_hockey":       [],
    "betcity_basketball":   [],
    "betcity_tennis":       [],
    "betcity_handball":     [],
    "betcity_rugby":        [],
    "betcity_volleyball":   [],
}

untranslated_cache = {
    "livescore":    set(),
    "hockey":       set(),
    "basketball":   set(),
    "tennis":       set(),
    "betcity":      set(),
    "hockeyBC":     set(),
    "basketballBC": set(),
    "tennisBC":     set(),
    "handballBC":   set(),
    "rugbyBC":      set(),
    "volleyballBC": set(),
}

# =========================
# NORMALIZATION
# =========================

SOCCER_PREFIX_MAP = {"fc": "", "cf": "", "fk": "", "kf": ""}

SOCCER_SUFFIX_MAP = {
    "u17": "(17)", "u18": "(18)", "u19": "(19)", "u20": "(20)",
    "u21": "(21)", "u22": "(22)", "u23": "(23)",
    "(a)": "(a)", "(w)": "(q)", "wfc": "(q)",
    "womens": "(q)", "women": "(q)", "ladies": "(q)",
    "reserves": "rezervi", "reserve": "rezervi",
    "w": "(q)", "fc": "", "cf": "", "fk": "", "kf": ""
}

HOCKEY_PREFIX_REMOVE = ["hk ", "hc "]
HOCKEY_SUFFIX_REMOVE = [" hk", " hc"]
HOCKEY_SUFFIX_MAP = {
    "u18": "(18)", "u19": "(19)", "u20": "(20)", "u23": "(23)",
    "(w)": "(q)", "3x3": "3X3", "womens": "(q)", "women": "(q)", "w": "(q)",
}


def normalize_team_name(name):
    name = name.strip()
    suffixes = []

    parts = name.split(" ", 1)
    if len(parts) > 1 and parts[0].lower() in SOCCER_PREFIX_MAP:
        name = parts[1].strip()

    while True:
        parts = name.rsplit(" ", 1)
        if len(parts) < 2:
            break
        last = parts[1].lower()
        if last in SOCCER_SUFFIX_MAP:
            if SOCCER_SUFFIX_MAP[last]:
                suffixes.insert(0, SOCCER_SUFFIX_MAP[last])
            name = parts[0].strip()
        else:
            break

    return name, " ".join(suffixes)


def normalize_hockey_livescore(name):
    name = name.strip()
    lower = name.lower()

    for p in HOCKEY_PREFIX_REMOVE:
        if lower.startswith(p):
            name = name[len(p):].strip()
            lower = name.lower()
            break

    for s in HOCKEY_SUFFIX_REMOVE:
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
        if last in HOCKEY_SUFFIX_MAP:
            mapped = HOCKEY_SUFFIX_MAP[last]
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

def get_livescore_period_scores(ev, sport):
    t1, t2 = [], []
    if sport == "hockey":
        for i in range(1, 4):
            v1, v2 = ev.get(f"Tr1Pe{i}"), ev.get(f"Tr2Pe{i}")
            if v1 is not None and v2 is not None:
                t1.append(str(v1)); t2.append(str(v2))
    elif sport == "basketball":
        for i in range(1, 5):
            v1, v2 = ev.get(f"Tr1Q{i}"), ev.get(f"Tr2Q{i}")
            if v1 is not None and v2 is not None:
                t1.append(str(v1)); t2.append(str(v2))
    elif sport == "tennis":
        for i in range(1, 6):
            v1, v2 = ev.get(f"Tr1S{i}"), ev.get(f"Tr2S{i}")
            if v1 is not None and v2 is not None:
                t1.append(str(v1)); t2.append(str(v2))
    if t1:
        return "[" + " ".join(t1) + "]", "[" + " ".join(t2) + "]"
    return "", ""


def get_betcity_period_scores(sc_add_ev):
    if not sc_add_ev or not sc_add_ev.strip():
        return "", ""
    t1, t2 = [], []
    for p in sc_add_ev.split(","):
        p = p.strip()
        if ":" in p:
            a, b = p.split(":", 1)
            t1.append(a.strip()); t2.append(b.strip())
    if t1:
        return "[" + " ".join(t1) + "]", "[" + " ".join(t2) + "]"
    return "", ""


# =========================
# TRANSLATION
# =========================

BETCITY_SUFFIX_MAPS = {
    "basketballBC": {
        " (3-х очк. попадания)": " (3 quliani)",
        " (2-х очк. попадания)": " (2 quliani)",
        " (подборы)": " (moxsna)",
        " (фолы)": " (foli)",
        " (заб. штрафные)": " (gat. jarimebi)",
        "(ж)": " (q)", "(шк.)": " (sk.)",
        "(3x3)": " (3/3)", "(3х3)": " (3/3)",
        "(шк)": " (sk)", "(сурд)": " (surd)", "(унив)": " (univ)",
        " (мол)": " (ax)", " (мол.)": " (ax)",
        " (Рез)": " (rez)", " (макк)": " (mak)",
    },
    "tennisBC": {
        " (геймы)": " (geim.)", " (пары)": " (wyv.)",
        " (дв. ошибки)": " (ormagi Secd.)",
        " (эйсы)": " (eisi)", " (srl)": " (srl)",
    },
    "handballBC": {
        " (мол)": " (ax)", " (ж)": " (q)", "(унив)": " (univ)",
        "(кол-во 2-х мин. уд.)": " (2wT gaZ. rao-ba)",
        "(7-метр. штр. бр.)": " (7-metr. saj. dar.)",
    },
    "rugbyBC": {" (ж)": " (q)"},
    "volleyballBC": {
        "(ж)": " (q)", "(люб)": " (moy)",
        "(4x4)": " (4/4)", "(4х4)": " (4/4)",
        "(микст)": " (mikst)", "(рез)": " (rez)",
        "(школ)": " (skol)", "(мол)": " (ax)",
        "(юноши)": " (iun)", "(воен)": " (samx)",
        "(унив)": " (univ)", "(кад)": " (kad)",
        "(мол. сб.)": " (ax. nak.)",
        "(ошибки на подачах)": " (Secdoma Cawodebaze)",
        "(эйсы)": " (eisi)", "(блоки)": " (bloki)",
        " (макк)": " (mak)", " (полиция)": " (policia)",
    },
}

COMMON_BETCITY_SUFFIX_MAP = {
    " (мол)": " (ax)", " (юн)": " (iun)", " (олимп)": " (olimp)",
    " (жен)": " (qal)", " (ж)": " (q)", " (люб)": " (moy)",
    " (люб.)": " (moyv)", " (резерв)": " (rezerv)",
    " (унив)": " (univ)", " (рез)": " (rez)",
    " (3x3)": " (3/3)", " (3х3)": " (3/3)",
    " (4x4)": " (4/4)", " (4х4)": " (4/4)",
    " (5x5)": " (5/5)", " (5х5)": " (5/5)",
    " (6x6)": " (6/6)", " (6х6)": " (6/6)",
    " (7x7)": " (6/6)", " (7х7)": " (6/6)",
    " (мини-футбол)": " (mini-fexb.)",
    " угл": "(kuTx.) ", " жк": "(yv.) ",
    " (штр)": " (saj)", " (бр)": " (dart)",
    " (сб. кл.)": " (kl. nak.)",
    " (2x2)": " (2/2)", " (2х2)": " (2/2)",
    " (нов)": " (ax)", " (до 18)": " (18-mde)", " (до 22)": " (22-mde)",
    " (сб. МХЛ)": " (nakr.МХЛ)", " (BCHL)": " (BCHL)",
    " (WHL)": " (dhl)", " (EJHL)": " (aihl)",
    " (голы в бол.)": " (goli met.)",
    " (выиг. вбрасывания)": " (Cagd. mogeba)",
    " (блок. бр.)": " (dart. blok.)",
    " (сил. приёмы)": " (Zal. ileTi)",
    " (видеопросмотры)": " (video Cveneba)",
}

BETCITY_PERIOD_SUFFIXES = {
    "basketballBC": [
        " (13)", " (14)", " (15)", " (16)", " (17)", " (18)", " (19)",
        " (20)", " (21)", " (22)", " (23)", " (24)", " (25)",
        " (40)", " (45)", " (50)", " (55)", " (45+)",
    ],
    "handballBC": [" (16)", " (17)", " (18)", " (19)", " (20)", " (21)", " (22)"],
    "rugbyBC":    [" (18)", " (19)", " (20)"],
    "volleyballBC": [
        " (14)", " (15)", " (16)", " (17)", " (18)", " (19)", " (20)",
        " (21)", " (22)", " (23)",
    ],
}


def _db_lookup(name, source):
    db = SessionLocal()
    result = db.query(Translation).filter(
        Translation.source_name == name,
        Translation.source == source
    ).first()
    db.close()
    if result:
        return result.georgian_name
    else:
        if source in untranslated_cache:
            untranslated_cache[source].add(name)
        return name


def translate_betcity_name(name, source):
    lower = name.strip().lower()
    collected_suffixes = []

    combined_map = {**COMMON_BETCITY_SUFFIX_MAP, **BETCITY_SUFFIX_MAPS.get(source, {})}

    # ვიწყებთ loop-ს: ვაგრძელებთ suffix-ების ამოღებას სანამ ახალი მოიძებნება
    while True:
        found = False

        # 1. BETCITY_PERIOD_SUFFIXES (მაგ: " (20)", " (45)")
        for ps in BETCITY_PERIOD_SUFFIXES.get(source, []):
            if lower.endswith(ps.lower()):
                collected_suffixes.insert(0, ps)
                lower = lower[:-len(ps)].strip()
                found = True
                break

        if not found:
            # 2. რეგექსი — (12)-(23) ტიპის period suffix
            m = re.search(r"\((1[2-9]|2[0-3])\)$", lower)
            if m:
                collected_suffixes.insert(0, " " + m.group(0))
                lower = lower[:m.start()].strip()
                found = True

        if not found:
            # 3. combined_map suffix-ები
            for k, v in combined_map.items():
                if lower.endswith(k.lower()):
                    collected_suffixes.insert(0, v)
                    lower = lower[:-len(k)].strip()
                    found = True
                    break

        # თუ ამ იტერაციაში ვერაფერი ამოვიღეთ — ვჩერდებით
        if not found:
            break

    # ФК / фк prefix ამოღება
    if lower.startswith("фк "):
        lower = lower[3:].strip()
    if lower.endswith(" фк"):
        lower = lower[:-3].strip()

    translated = _db_lookup(lower, source)
    suffix_str = "".join(collected_suffixes).strip()
    return (translated + (" " + suffix_str if suffix_str else "")).strip()


def _translate_pair(name, source, single_fn):
    """/ სიმბოლოთი გამოყოფილი წყვილები ცალ-ცალკე ითარგმნება"""
    sep = "/" if source == "tennisBC" else " / "
    if sep in name:
        a, b = name.split(sep, 1)
        return single_fn(a.strip(), source) + " / " + single_fn(b.strip(), source)
    return single_fn(name.strip(), source)


def translate(name, source):
    if source in ("betcity", "hockeyBC", "basketballBC", "handballBC", "rugbyBC", "volleyballBC"):
        return translate_betcity_name(name, source)

    if source == "tennisBC":
        return _translate_pair(name, source, translate_betcity_name)

    clean_name, suffix = normalize_team_name(name)
    translated = _db_lookup(clean_name.lower(), source)
    return (translated + (" " + suffix if suffix else "")).strip()


def translate_tennis_livescore(name, source):
    return _translate_pair(name, source, lambda n, s: translate(n, s))


# =========================
# LIVESCORE
# =========================

def fetch_livescore_sport(sport, source_key, sport_icon):
    url = f"https://prod-public-api.livescore.com/v1/api/app/date/{sport}/{get_today()}/4?countryCode=GE&locale=en&MD=1"
    try:
        data = requests.get(url, timeout=10).json()
    except:
        return []

    matches = []
    for stage in data.get("Stages", []):
        league  = stage.get("Snm", "")
        country = stage.get("Cnm") or ""
        flag    = livescore_flags.get(country.strip()) or livescore_flags.get(country.strip().title())

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
                score1, score2, minute = str(ev.get("Tr1", 0)), str(ev.get("Tr2", 0)), ft
            else:
                score1, score2 = "?", "?"
                esd = str(ev.get("Esd", ""))
                minute = f"{esd[8:10]}:{esd[10:12]}" if esd else ""

            if re.match(r'^\d{2}:\d{2}$', minute):
                continue

            period1, period2 = get_livescore_period_scores(ev, sport) if sport in ("hockey", "basketball", "tennis") else ("", "")

            if sport == "hockey":
                clean1, suf1 = normalize_hockey_livescore(team1)
                clean2, suf2 = normalize_hockey_livescore(team2)
                t1 = translate(clean1, source_key) + (" " + suf1 if suf1 else "")
                t2 = translate(clean2, source_key) + (" " + suf2 if suf2 else "")
            elif sport == "tennis":
                t1 = translate_tennis_livescore(team1, source_key)
                t2 = translate_tennis_livescore(team2, source_key)
            else:
                t1 = translate(team1, source_key)
                t2 = translate(team2, source_key)

            matches.append({
                "league": league, "country": country, "minute": minute,
                "team1": t1, "score1": score1, "score2": score2,
                "period1": period1, "period2": period2,
                "team2": t2, "flag": flag,
                "sport_icon": sport_icon, "source": "livescore"
            })

    return matches


def fetch_livescore():            return fetch_livescore_sport("soccer",     "livescore",   "Soccer.gif")
def fetch_livescore_hockey():     return fetch_livescore_sport("hockey",     "hockey",      "Hockey.gif")
def fetch_livescore_basketball(): return fetch_livescore_sport("basketball", "basketball",  "Basketball.gif")
def fetch_livescore_tennis():     return fetch_livescore_sport("tennis",     "tennis",      "Tennis.gif")


# =========================
# BETCITY
# =========================

def fetch_betcity_sport(sport_keyword, source_key, sport_icon, skip_keywords=None):
    url = "https://ap.betcityru.com/api/v1/live/results?rev=3&ver=96&csn=f9xg7b"
    try:
        data = requests.get(url, timeout=10).json()
    except:
        return []

    matches = []
    skip_keywords = skip_keywords or []
    sports = data.get("reply", {}).get("sports", {})

    for sp in sports.values():
        if sport_keyword not in sp.get("name_sp", "").lower():
            continue

        for ch in sp.get("chmps", {}).values():
            league = ch.get("name_ch", "")
            if any(kw in league.lower() for kw in skip_keywords):
                continue

            flag = next((v for k, v in betcity_flags.items() if " " + k.lower() in league.lower()), None)

            for ev in ch.get("evts", {}).values():
                score_clean = re.sub(r'^[А-Яа-яA-Za-z]+\s+', '', ev.get("sc_ev", "")).strip()
                if ":" in score_clean:
                    s1, s2 = score_clean.split(":", 1)
                    score1, score2 = s1.strip(), s2.strip()
                else:
                    score1, score2 = "?", "?"

                period1, period2 = get_betcity_period_scores(ev.get("sc_add_ev", ""))
                minute = "FT" if ev.get("st_ev") == 2 else ""

                matches.append({
                    "league": league, "country": "", "minute": minute,
                    "team1": translate(ev.get("name_ht", "").strip(), source_key),
                    "score1": score1, "score2": score2,
                    "period1": period1, "period2": period2,
                    "team2": translate(ev.get("name_at", "").strip(), source_key),
                    "flag": flag, "sport_icon": sport_icon, "source": "betcity"
                })

    return matches


def fetch_betcity():            return fetch_betcity_sport("футбол",    "betcity",      "Soccer.gif",     ["киберфутбол", "статистика", "австралийский футбол", "пляжный футбол", "мини-футбол"])
def fetch_betcity_hockey():     return fetch_betcity_sport("хоккей",    "hockeyBC",     "Hockey.gif",     ["статистика", "киберхоккей", "хоккей на траве"])
def fetch_betcity_basketball(): return fetch_betcity_sport("баскетбол", "basketballBC", "Basketball.gif", ["статистика", "кибербаскетбол"])
def fetch_betcity_tennis():     return fetch_betcity_sport("теннис",    "tennisBC",     "Tennis.gif",     ["статистика", "настольный теннис", "падел-теннис"])
def fetch_betcity_handball():   return fetch_betcity_sport("гандбол",   "handballBC",   "Handball.gif",   ["статистика"])
def fetch_betcity_rugby():      return fetch_betcity_sport("регби",     "rugbyBC",      "Rugby.gif",      ["статистика"])
def fetch_betcity_volleyball(): return fetch_betcity_sport("волейбол",  "volleyballBC", "Volleyball.gif", ["статистика"])


# =========================
# CACHE
# =========================

def update_matches():
    for key in untranslated_cache:
        untranslated_cache[key].clear()

    matches_cache["livescore"]            = fetch_livescore()
    matches_cache["livescore_hockey"]     = fetch_livescore_hockey()
    matches_cache["livescore_basketball"] = fetch_livescore_basketball()
    matches_cache["livescore_tennis"]     = fetch_livescore_tennis()
    matches_cache["betcity"]              = fetch_betcity()
    matches_cache["betcity_hockey"]       = fetch_betcity_hockey()
    matches_cache["betcity_basketball"]   = fetch_betcity_basketball()
    matches_cache["betcity_tennis"]       = fetch_betcity_tennis()
    matches_cache["betcity_handball"]     = fetch_betcity_handball()
    matches_cache["betcity_rugby"]        = fetch_betcity_rugby()
    matches_cache["betcity_volleyball"]   = fetch_betcity_volleyball()


def get_all_matches():
    result = []
    for key in matches_cache:
        result.extend(matches_cache[key])
    return result
