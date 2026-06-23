"""official card catalog + images

Adds two tables that let the official competition data (card metadata + card
images) live in the database instead of as large files in the repo:

* ``official_cards``        — one row per unique Card ID (metadata + attacks JSON)
* ``official_card_images``  — the card image bytes, keyed by Card ID

Idempotent: uses ``create_all`` against the migration's connection, which only
emits CREATE TABLE for tables that don't already exist (safe on fresh and
established databases). Populate the data with ``tools/load_official_data.py``.

Revision ID: 0002_official_cards
Revises: 0001_baseline
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

from db.database import Base
from db import models  # noqa: F401  (register all tables on Base.metadata)

revision = "0002_official_cards"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

_TABLES = ["official_cards", "official_card_images"]


def upgrade() -> None:
    bind = op.get_bind()
    # create_all emits CREATE TABLE only for missing tables → safe to re-run.
    Base.metadata.create_all(bind=bind, tables=[
        Base.metadata.tables[t] for t in _TABLES if t in Base.metadata.tables
    ])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())
    for table in reversed(_TABLES):
        if table in existing:
            op.drop_table(table)
