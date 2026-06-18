"""ORM models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    games: Mapped[list["GameRecord"]] = relationship(back_populates="user")


class GameRecord(Base):
    """A finished game saved by a logged-in user (results history)."""
    __tablename__ = "game_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(32))
    deck_a: Mapped[str] = mapped_column(String(64))
    deck_b: Mapped[str] = mapped_column(String(64))
    agent_a: Mapped[str] = mapped_column(String(32))
    agent_b: Mapped[str] = mapped_column(String(32))
    winner: Mapped[str] = mapped_column(String(32), nullable=True)
    turns: Mapped[int] = mapped_column(Integer, default=0)
    log: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="games")


class Submission(Base):
    """An AI training agent entered on the skill-rating ladder.

    Skill is a Gaussian N(mu, sigma^2). ``status`` moves validating -> active
    once the self-mirror validation game passes (or -> error with logs)."""
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False)   # registry model
    deck: Mapped[str] = mapped_column(String(64), default="rotating")    # or a deck id
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)

    mu: Mapped[float] = mapped_column(default=600.0)
    sigma: Mapped[float] = mapped_column(default=200.0)
    games: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String(16), default="validating")  # validating|active|error
    error_log: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    history: Mapped[list["RatingPoint"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan")


class RatingPoint(Base):
    """A snapshot of a submission's rating after a game — the progress curve."""
    __tablename__ = "rating_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id"), index=True)
    games: Mapped[int] = mapped_column(Integer, default=0)
    mu: Mapped[float] = mapped_column(default=600.0)
    sigma: Mapped[float] = mapped_column(default=200.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submission: Mapped["Submission"] = relationship(back_populates="history")


class Episode(Base):
    """One ladder match between two submissions (audit log)."""
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sub_a_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    sub_b_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    deck_a: Mapped[str] = mapped_column(String(64))
    deck_b: Mapped[str] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(8))   # a|b|draw
    turns: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ModelStat(Base):
    """Lifetime aggregate score for an agent/model across *every* game it plays
    (Watch, Play vs AI, Model Arena, and ladder episodes)."""
    __tablename__ = "model_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    games: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CardImageOverride(Base):
    """A user-supplied replacement image URL for a card whose art is missing or
    broken. Applied wherever card art is shown (Card Explorer and the board)."""
    __tablename__ = "card_image_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
