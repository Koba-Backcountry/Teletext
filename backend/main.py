from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import inspect

from db import Base, engine, SessionLocal
from loader import load_translations, load_flags
from scheduler import scheduler
from services import get_all_matches, update_matches, untranslated_cache
from models import User, Translation

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = "gt-secret-2024-xK9mP"

def verify_key(x_api_key: Optional[str] = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if "users" not in inspect(engine).get_table_names() or db.query(User).count() == 0:
        db.add(User(username="admin", password="admin", is_approved=1, is_admin=1))
        db.commit()

    if db.query(Translation).count() == 0:
        load_translations()

    db.close()
    load_flags()
    scheduler.start()
    update_matches()


# =====================
# PUBLIC ENDPOINTS
# =====================

@app.get("/matches")
def matches():
    return get_all_matches()


class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class AdminUpdate(BaseModel):
    username: str
    password: str


@app.post("/register")
def register(user: UserCreate):
    db = SessionLocal()
    if db.query(User).filter(User.username == user.username).first():
        db.close()
        return {"status": "exists"}
    db.add(User(username=user.username, password=user.password, is_approved=0, is_admin=0))
    db.commit()
    db.close()
    return {"status": "ok"}


@app.post("/login")
def login(user: UserLogin):
    db = SessionLocal()
    u = db.query(User).filter(User.username == user.username).first()
    db.close()
    if not u or u.password != user.password:
        return {"status": "invalid"}
    if u.is_approved == 0:
        return {"status": "pending"}
    return {"status": "ok", "is_admin": 1 if u.is_admin == 1 else 0}


# =====================
# PROTECTED ENDPOINTS
# =====================

@app.get("/pending-users")
def pending_users(_=Depends(verify_key)):
    db = SessionLocal()
    users = db.query(User).filter(User.is_approved == 0).all()
    result = [{"id": u.id, "username": u.username} for u in users]
    db.close()
    return result


@app.get("/approved-users")
def approved_users(_=Depends(verify_key)):
    db = SessionLocal()
    users = db.query(User).filter(User.is_approved == 1, User.is_admin == 0).all()
    result = [{"id": u.id, "username": u.username} for u in users]
    db.close()
    return result


@app.post("/approve/{user_id}")
def approve_user(user_id: int, _=Depends(verify_key)):
    db = SessionLocal()
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        db.close()
        return {"status": "not_found"}
    u.is_approved = 1
    db.commit()
    db.close()
    return {"status": "ok"}


@app.post("/set-pending/{user_id}")
def set_pending(user_id: int, _=Depends(verify_key)):
    db = SessionLocal()
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        db.close()
        return {"status": "not_found"}
    u.is_approved = 0
    db.commit()
    db.close()
    return {"status": "ok"}


@app.post("/admin/update")
def update_admin(data: AdminUpdate, _=Depends(verify_key)):
    db = SessionLocal()
    admin = db.query(User).filter(User.is_admin == 1).first()
    if not admin:
        db.close()
        return {"status": "not_found"}
    admin.username = data.username
    admin.password = data.password
    db.commit()
    db.close()
    return {"status": "ok"}


@app.get("/untranslated", response_class=PlainTextResponse)
def get_untranslated(_=Depends(verify_key)):
    sections = [
        ("livescore_soccer",     "livescore"),
        ("livescore_hockey",     "hockey"),
        ("livescore_basketball", "basketball"),
        ("livescore_tennis",     "tennis"),
        ("betcity_Футбол",       "betcity"),
        ("betcity_Хоккей",       "hockeyBC"),
        ("betcity_Баскетбол",    "basketballBC"),
        ("betcity_Теннис",       "tennisBC"),
        ("betcity_Гандбол",      "handballBC"),
        ("betcity_Регби",        "rugbyBC"),
        ("betcity_Волейбол",     "volleyballBC"),
    ]
    lines = []
    for label, key in sections:
        lines.append(label)
        for name in sorted(untranslated_cache.get(key, set())):
            lines.append(name)
    return "\n".join(lines)
