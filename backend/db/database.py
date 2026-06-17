"""Database setup.

Connection is driven entirely by the ``DATABASE_URL`` environment variable:
  * Local Docker  -> postgresql+psycopg2://tcg:tcg@db:5432/tcg  (docker-compose)
  * Neon (prod)   -> postgresql+psycopg2://USER:PASS@HOST/DB?sslmode=require
  * Dev fallback  -> SQLite file (when DATABASE_URL is unset), so the app runs
                     even without a Postgres instance handy.

Neon requires SSL; pass ``?sslmode=require`` in the URL (the README shows how).
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(os.path.dirname(__file__), "..", "tcg_dev.db"),
)

# Normalise the scheme some providers hand out ("postgres://" -> psycopg2).
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (register models)
    Base.metadata.create_all(bind=engine)
