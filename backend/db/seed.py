"""Seed the database with an initial admin user.

Idempotent: safe to run on every startup. Credentials come from env vars so
they can be overridden in production; defaults match the project owner's
request. The password is stored bcrypt-hashed — change it after first login.

  ADMIN_USERNAME (default: admin)
  ADMIN_EMAIL    (default: steeleschauer@gmail.com)
  ADMIN_PASSWORD (default: tmppassword)
"""
from __future__ import annotations

import os

from sqlalchemy.orm import Session

from db.database import SessionLocal, init_db
from db.models import User
from auth.security import hash_password


def seed_admin() -> None:
    init_db()
    username = os.environ.get("ADMIN_USERNAME", "admin")
    email = os.environ.get("ADMIN_EMAIL", "steeleschauer@gmail.com")
    password = os.environ.get("ADMIN_PASSWORD", "tmppassword")

    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            # keep it an admin; don't overwrite a changed password
            if not existing.is_admin:
                existing.is_admin = True
                db.commit()
            print(f"[seed] admin '{existing.username}' already present.")
            return
        admin = User(
            username=username, email=email,
            hashed_password=hash_password(password), is_admin=True,
        )
        db.add(admin)
        db.commit()
        print(f"[seed] created admin '{username}' <{email}>.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
