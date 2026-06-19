#!/usr/bin/env python3
"""Extract per-card images from a Pokémon "Card ID List" PDF into
``frontend/public/assets/cards/<CardID>.png`` so the app's *Official card data*
toggle can show them (pattern ``assets/cards/{id}.png``).

How it works
------------
The PDF's first pages are a table of contents whose rows each link to that
card's image page. We read those GOTO link annotations, pair each link with the
Card ID printed on its row, then export the image on the linked page.

Usage
-----
    pip install pymupdf
    python tools/extract_card_images.py \
        --pdf "frontend/public/assets/Card_ID List_EN.pdf" \
        --out frontend/public/assets/cards

Notes
-----
* The EN "Card ID List" PDF stores **black-and-white** art (text/frames are
  crisp; the illustrations are 1-bit). Point ``--pdf`` at a colour PDF (e.g. a
  colour JP list) to get colour images instead — the mapping is identical.
* Images are written at their native embedded resolution. This is a one-time,
  local step; keep the assets out of git (they're large and licensed for
  competition use only).
"""
from __future__ import annotations

import argparse
import os
import re
import sys


def build_id_to_page(doc):
    """Map Card ID -> 0-based page index using TOC link annotations."""
    import fitz
    id2page: dict[int, int] = {}
    # TOC pages are the ones before the first page that carries a card image.
    first_img = next((p for p in range(doc.page_count) if doc[p].get_images()), doc.page_count)
    for p in range(first_img):
        page = doc[p]
        words = page.get_text("words")  # (x0,y0,x1,y1,word,...)
        nums = [(w[0], (w[1] + w[3]) / 2, int(w[4])) for w in words if re.fullmatch(r"\d+", w[4])]
        for link in page.get_links():
            if link.get("kind") != fitz.LINK_GOTO:
                continue
            ymid = (link["from"].y0 + link["from"].y1) / 2
            row = [(x0, val) for (x0, y, val) in nums if abs(y - ymid) < 7]
            if row:
                cid = min(row, key=lambda t: t[0])[1]   # leftmost number on the row = Card ID
                id2page.setdefault(cid, link["page"])
    return id2page


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default="frontend/public/assets/Card_ID List_EN.pdf")
    ap.add_argument("--out", default="frontend/public/assets/cards")
    ap.add_argument("--render", action="store_true",
                    help="rasterize the page region instead of extracting the embedded image "
                         "(use if a colour PDF composites image+mask and raw extraction looks wrong)")
    ap.add_argument("--dpi", type=int, default=200, help="DPI for --render mode")
    args = ap.parse_args(argv)

    try:
        import fitz  # PyMuPDF
    except ImportError:
        sys.exit("PyMuPDF is required:  pip install pymupdf")

    if not os.path.isfile(args.pdf):
        sys.exit(f"PDF not found: {args.pdf}")
    os.makedirs(args.out, exist_ok=True)

    doc = fitz.open(args.pdf)
    id2page = build_id_to_page(doc)
    if not id2page:
        sys.exit("No Card ID -> page links found; is this a 'Card ID List' PDF?")
    print(f"Mapped {len(id2page)} cards (IDs {min(id2page)}-{max(id2page)}). Writing to {args.out} …")

    written = 0
    for cid, pidx in sorted(id2page.items()):
        page = doc[pidx]
        imgs = page.get_images(full=True)
        if not imgs:
            continue
        out = os.path.join(args.out, f"{cid}.png")
        if args.render:
            xref = imgs[0][0]
            rects = page.get_image_rects(xref)
            clip = rects[0] if rects else page.rect
            mat = fitz.Matrix(args.dpi / 72, args.dpi / 72)
            page.get_pixmap(matrix=mat, clip=clip, alpha=False).save(out)
        else:
            xref = imgs[0][0]
            info = doc.extract_image(xref)          # native embedded bytes
            with open(out, "wb") as fh:
                fh.write(info["image"])
        written += 1
        if written % 200 == 0:
            print(f"  …{written}")
    print(f"Done: wrote {written} card images to {args.out}")


if __name__ == "__main__":
    main()
