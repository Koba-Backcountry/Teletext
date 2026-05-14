from db import SessionLocal
from models import Translation

livescore_flags = {}
betcity_flags = {}

def load_translations():
    db = SessionLocal()

    # Soccer (Livescore)
    with open("/Bases/gundebi.txt", encoding="utf-8") as f:
        for line in f:
            eng = line[:49].strip().lower()
            geo = line[49:].strip()
            if eng:
                db.add(Translation(source_name=eng, georgian_name=geo, source="livescore"))

    # Hockey (Livescore)
    with open("/Bases/hockey.txt", encoding="utf-8") as f:
        for line in f:
            eng = line[:42].strip().lower()
            geo = line[42:].strip()
            if eng:
                db.add(Translation(source_name=eng, georgian_name=geo, source="hockey"))

    # Basketball (Livescore)
    with open("/Bases/basketball.txt", encoding="utf-8") as f:
        for line in f:
            eng = line[:42].strip().lower()
            geo = line[42:].strip()
            if eng:
                db.add(Translation(source_name=eng, georgian_name=geo, source="basketball"))

    # Tennis (Livescore)
    with open("/Bases/gvarebi.txt", encoding="utf-8") as f:
        for line in f:
            eng = line[:42].strip().lower()
            geo = line[42:].strip()
            if eng:
                db.add(Translation(source_name=eng, georgian_name=geo, source="tennis"))

    # Soccer (Betcity)
    with open("/Bases/soccerBC.txt", encoding="utf-8") as f:
        for line in f:
            ru = line[:42].strip().lower()
            geo = line[42:].strip()
            if ru:
                db.add(Translation(source_name=ru, georgian_name=geo, source="betcity"))

    # Hockey (Betcity)
    with open("/Bases/hockeyBC.txt", encoding="utf-8") as f:
        for line in f:
            ru = line[:42].strip().lower()
            geo = line[42:].strip()
            if ru:
                db.add(Translation(source_name=ru, georgian_name=geo, source="hockeyBC"))

    # Basketball (Betcity)
    with open("/Bases/basketballBC.txt", encoding="utf-8") as f:
        for line in f:
            ru = line[:42].strip().lower()
            geo = line[42:].strip()
            if ru:
                db.add(Translation(source_name=ru, georgian_name=geo, source="basketballBC"))

    # Tennis (Betcity)
    with open("/Bases/tennisBC.txt", encoding="utf-8") as f:
        for line in f:
            ru = line[:42].strip().lower()
            geo = line[42:].strip()
            if ru:
                db.add(Translation(source_name=ru, georgian_name=geo, source="tennisBC"))

    # Handball (Betcity)
    with open("/Bases/handballBC.txt", encoding="utf-8") as f:
        for line in f:
            ru = line[:42].strip().lower()
            geo = line[42:].strip()
            if ru:
                db.add(Translation(source_name=ru, georgian_name=geo, source="handballBC"))

    # Rugby (Betcity)
    with open("/Bases/rugbyBC.txt", encoding="utf-8") as f:
        for line in f:
            ru = line[:42].strip().lower()
            geo = line[42:].strip()
            if ru:
                db.add(Translation(source_name=ru, georgian_name=geo, source="rugbyBC"))

    # Volleyball (Betcity)
    with open("/Bases/volleyballBC.txt", encoding="utf-8") as f:
        for line in f:
            ru = line[:42].strip().lower()
            geo = line[42:].strip()
            if ru:
                db.add(Translation(source_name=ru, georgian_name=geo, source="volleyballBC"))

    db.commit()
    db.close()


def load_flags():
    global livescore_flags, betcity_flags

    # Livescore flags
    with open("/Flags LiveScore.txt", encoding="utf-8") as f:
        for line in f:
            if "'" in line:
                parts = line.split("'")
                if len(parts) >= 4:
                    name = parts[1]
                    flag = parts[3]
                    livescore_flags[name] = flag

    # Betcity flags
    with open("/Flags BetCity.txt", encoding="utf-8") as f:
        for line in f:
            if "'" in line:
                parts = line.split("'")
                if len(parts) >= 4:
                    name = parts[1]
                    flag = parts[3]
                    betcity_flags[name] = flag
