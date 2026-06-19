#!/usr/bin/env python3
"""Load the official competition card data into the database so the large source
files can be removed from the repo.

* metadata  ← en_card_data.csv  → ``official_cards`` (one row per Card ID; the
  CSV is denormalized by attack, so attacks are aggregated into a JSON ``moves``)
* images    ← Card_ID List PDF  → ``official_card_images`` (PNG bytes per Card ID)

Targets whatever ``DATABASE_URL`` points at (Postgres/Neon in production, sqlite
locally). Idempotent — re-running upserts.

Usage
-----
    pip install pymupdf pandas
    # local sqlite (backend/tcg_dev.db):
    python tools/load_official_data.py \
        --csv "frontend/public/assets/en_card_data.csv" \
        --pdf "frontend/public/assets/Card_ID List_EN.pdf"

    # production Postgres (Neon):
    DATABASE_URL="postgresql://…?sslmode=require" \
    python tools/load_official_data.py --csv en_card_data.csv --pdf "Card_ID List_EN.pdf"

Options: --skip-images (metadata only), --database-url URL (overrides env).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(os.path.dirname(HERE), "backend")


def _clean(v):
    """CSV cell -> trimmed string; floats like 200.0 -> '200'; NaN/None -> ''."""
    if v is None:
        return ""
    if isinstance(v, float):
        if v != v:               # NaN
            return ""
        return str(int(v)) if v == int(v) else str(v)
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def read_cards(csv_path):
    import pandas as pd
    df = pd.read_csv(csv_path)
    df = df.where(df.notnull(), None)
    col = {c.lower().strip(): c for c in df.columns}

    def C(*names):
        for n in names:
            if n in col:
                return col[n]
        return None

    c_id = C("card id")
    c_name = C("card name")
    c_exp = C("expansion")
    c_no = C("collection no.", "collection no")
    c_stage = C("stage (pokémon)/type (energy and trainer)",
                "stage (pokémon) / type (energy and trainer)", "stage")
    c_cat = C("category")
    c_hp = C("hp")
    c_type = C("type")
    c_weak = C("weakness")
    c_res = C("resistance (type)", "resistance")
    c_ret = C("retreat")
    c_mv = C("move name")
    c_cost = C("cost")
    c_dmg = C("damage")
    c_eff = C("effect explanation")

    cards: dict[int, dict] = {}
    for _, r in df.iterrows():
        if c_id is None or r[c_id] is None:
            continue
        cid = int(r[c_id])
        c = cards.setdefault(cid, {
            "card_id": cid, "name": "", "expansion": "", "collection_no": "",
            "stage": "", "category": "", "hp": "", "type": "", "weakness": "",
            "resistance": "", "retreat": "", "moves": [],
        })

        def setf(key, src):
            if src is not None and not c[key]:
                val = _clean(r[src])
                if val:
                    c[key] = val
        setf("name", c_name); setf("expansion", c_exp); setf("collection_no", c_no)
        setf("stage", c_stage); setf("category", c_cat); setf("hp", c_hp)
        setf("type", c_type); setf("weakness", c_weak); setf("resistance", c_res)
        setf("retreat", c_ret)
        mv = _clean(r[c_mv]) if c_mv else ""
        if mv:
            c["moves"].append({
                "name": mv,
                "cost": _clean(r[c_cost]) if c_cost else "",
                "damage": _clean(r[c_dmg]) if c_dmg else "",
                "effect": _clean(r[c_eff]) if c_eff else "",
            })
    return cards


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="frontend/public/assets/en_card_data.csv")
    ap.add_argument("--pdf", default="frontend/public/assets/Card_ID List_EN.pdf")
    ap.add_argument("--skip-images", action="store_true")
    ap.add_argument("--database-url", default=None,
                    help="override DATABASE_URL (else uses the env / sqlite fallback)")
    args = ap.parse_args(argv)

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    # import DB layer AFTER setting DATABASE_URL (it's read at import time)
    sys.path.insert(0, BACKEND)
    from db.database import SessionLocal, engine, Base
    from db import models  # noqa: F401  (register tables)
    from db.models import OfficialCard, OfficialCardImage
    Base.metadata.create_all(bind=engine)   # works even if alembic hasn't run

    if not os.path.isfile(args.csv):
        sys.exit(f"CSV not found: {args.csv}")
    cards = read_cards(args.csv)
    print(f"Parsed {len(cards)} unique cards from {args.csv}. Writing metadata …")

    db = SessionLocal()
    try:
        for cid, c in cards.items():
            db.merge(OfficialCard(
                card_id=cid, name=c["name"], expansion=c["expansion"],
                collection_no=c["collection_no"], stage=c["stage"],
                category=c["category"], hp=c["hp"], type=c["type"],
                weakness=c["weakness"], resistance=c["resistance"],
                retreat=c["retreat"], moves=json.dumps(c["moves"]),
            ))
        db.commit()
        print(f"  metadata: {len(cards)} cards upserted.")

        if not args.skip_images:
            if not os.path.isfile(args.pdf):
                sys.exit(f"PDF not found: {args.pdf} (use --skip-images to load metadata only)")
            try:
                import fitz  # noqa: F401
            except ImportError:
                sys.exit("PyMuPDF required for images:  pip install pymupdf")
            import fitz
            sys.path.insert(0, HERE)
            from extract_card_images import build_id_to_page
            doc = fitz.open(args.pdf)
            id2page = build_id_to_page(doc)
            print(f"Extracting {len(id2page)} images from {args.pdf} …")
            n = 0
            for cid, pidx in id2page.items():
                imgs = doc[pidx].get_images(full=True)
                if not imgs:
                    continue
                info = doc.extract_image(imgs[0][0])
                mime = "image/png" if info["ext"] == "png" else f"image/{info['ext']}"
                db.merge(OfficialCardImage(card_id=cid, mime=mime, data=info["image"]))
                n += 1
                if n % 200 == 0:
                    db.commit(); print(f"  …{n}")
            db.commit()
            print(f"  images: {n} upserted.")
        print("Done. You can now remove the CSV/PDF/cards from the repo.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
