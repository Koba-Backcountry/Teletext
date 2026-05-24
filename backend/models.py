from sqlalchemy import Column, Integer, String
from db import Base

class Translation(Base):
    __tablename__ = "translations"

    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String, index=True)
    georgian_name = Column(String)
    source = Column(String)  # livescore / betcity

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    is_approved = Column(Integer, default=0)  # 0 = არა, 1 = კი
    is_admin = Column(Integer, default=0)     # 1 = შენი სუპერ იუზერი
