from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from db import Base, engine, SessionLocal
from loader import load_translations, load_flags
from scheduler import scheduler
from services import get_all_matches, update_matches
from models import User, Translation
from sqlalchemy import inspect
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# API KEY
# =========================

API_KEY = "gt-secret-2024-xK9mP"

def verify_key(x_api_key: Optional[str] = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    inspector = inspect(engine)

    # =========================
    # CREATE DEFAULT ADMIN
    # =========================

    if "users" in inspector.get_table_names():
        users_count = db.query(User).count()
    else:
        users_count = 0

    if users_count == 0:
        db.add(User(
            username="admin",
            password="admin",
            is_approved=1,
            is_admin=1
        ))
        db.commit()

    # =========================
    # LOAD TRANSLATIONS ONLY ONCE
    # =========================

    translations_count = db.query(Translation).count()

    if translations_count == 0:
        load_translations()

    db.close()

    # =========================
    # LOAD FLAGS + START SYSTEM
    # =========================

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


@app.post("/register")
def register(user: UserCreate):
    db = SessionLocal()

    exists = db.query(User).filter(User.username == user.username).first()

    if exists:
        db.close()
        return {"status": "exists"}

    new_user = User(
        username=user.username,
        password=user.password,
        is_approved=0,
        is_admin=0
    )

    db.add(new_user)
    db.commit()
    db.close()

    return {"status": "ok"}


class UserLogin(BaseModel):
    username: str
    password: str


@app.post("/login")
def login(user: UserLogin):
    db = SessionLocal()

    u = db.query(User).filter(User.username == user.username).first()

    if not u or u.password != user.password:
        db.close()
        return {"status": "invalid"}

    if u.is_approved == 0:
        db.close()
        return {"status": "pending"}

    db.close()

    return {
        "status": "ok",
        "is_admin": 1 if u.is_admin == 1 else 0
    }


# =====================
# PROTECTED ENDPOINTS
# =====================

@app.get("/pending-users")
def pending_users(x_api_key: Optional[str] = Header(None)):
    verify_key(x_api_key)
    db = SessionLocal()

    users = db.query(User).filter(User.is_approved == 0).all()

    result = [{"id": u.id, "username": u.username} for u in users]

    db.close()
    return result


@app.post("/approve/{user_id}")
def approve_user(user_id: int, x_api_key: Optional[str] = Header(None)):
    verify_key(x_api_key)
    db = SessionLocal()

    u = db.query(User).filter(User.id == user_id).first()

    if not u:
        db.close()
        return {"status": "not_found"}

    u.is_approved = 1
    db.commit()
    db.close()

    return {"status": "ok"}


class AdminUpdate(BaseModel):
    username: str
    password: str


@app.post("/admin/update")
def update_admin(data: AdminUpdate, x_api_key: Optional[str] = Header(None)):
    verify_key(x_api_key)
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


@app.get("/approved-users")
def approved_users(x_api_key: Optional[str] = Header(None)):
    verify_key(x_api_key)
    db = SessionLocal()

    users = db.query(User).filter(
        User.is_approved == 1,
        User.is_admin == 0
    ).all()

    result = [{"id": u.id, "username": u.username} for u in users]

    db.close()
    return result


@app.post("/set-pending/{user_id}")
def set_pending(user_id: int, x_api_key: Optional[str] = Header(None)):
    verify_key(x_api_key)
    db = SessionLocal()

    u = db.query(User).filter(User.id == user_id).first()

    if not u:
        db.close()
        return {"status": "not_found"}

    u.is_approved = 0
    db.commit()
    db.close()

    return {"status": "ok"}
