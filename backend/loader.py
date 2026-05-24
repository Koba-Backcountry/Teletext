from db import SessionLocal
from models import Translation

livescore_flags = {}
betcity_flags = {}

TRANSLATION_FILES = [
    ("/Bases/gundebi.txt",      49, "livescore"),
    ("/Bases/hockey.txt",       42, "hockey"),
    ("/Bases/basketball.txt",   42, "basketball"),
    ("/Bases/gvarebi.txt",      42, "tennis"),
    ("/Bases/soccerBC.txt",     42, "betcity"),
    ("/Bases/hockeyBC.txt",     42, "hockeyBC"),
    ("/Bases/basketballBC.txt", 42, "basketballBC"),
    ("/Bases/tennisBC.txt",     42, "tennisBC"),
    ("/Bases/handballBC.txt",   42, "handballBC"),
    ("/Bases/rugbyBC.txt",      42, "rugbyBC"),
    ("/Bases/volleyballBC.txt", 42, "volleyballBC"),
]

def load_translations():
    db = SessionLocal()
    for path, col_width, source in TRANSLATION_FILES:
        with open(path, encoding="utf-8") as f:
            for line in f:
                name = line[:col_width].strip().lower()
                geo  = line[col_width:].strip()
                if name:
                    db.add(Translation(source_name=name, georgian_name=geo, source=source))
    db.commit()
    db.close()


def _load_flag_file(path, flag_dict):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "'" in line:
                parts = line.split("'")
                if len(parts) >= 4:
                    flag_dict[parts[1]] = parts[3]

def load_flags():
    global livescore_flags, betcity_flags
    _load_flag_file("/Flags LiveScore.txt", livescore_flags)
    _load_flag_file("/Flags BetCity.txt",   betcity_flags)
