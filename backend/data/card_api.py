"""Official card-list integration.

Pulls live card data from the public Pokémon TCG API (https://pokemontcg.io)
so the UI can browse the *latest* Standard-legal sets, card text, and official
artwork. Results are cached to disk so the app stays responsive and works
offline after the first fetch; if the API is unreachable, we fall back to the
hand-authored catalogue so the app never hard-fails.

Important distinction:
  * This module supplies *card data* (names, images, text, set legality).
  * Playable *rules* for a card live in ``engine/effects.py``. A card is
    "battle-ready" only when its effects are implemented; everything else is
    still fully browsable in the Card Explorer.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.parse
from typing import Any, Optional

API_BASE = "https://api.pokemontcg.io/v2"
CACHE_DIR = os.environ.get("CARD_CACHE_DIR", os.path.join(os.path.dirname(__file__), "..", ".card_cache"))
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL = 60 * 60 * 24  # 1 day


def _cache_path(key: str) -> str:
    safe = urllib.parse.quote(key, safe="")
    return os.path.join(CACHE_DIR, f"{safe}.json")


def _read_cache(key: str) -> Optional[Any]:
    path = _cache_path(key)
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < CACHE_TTL:
        try:
            with open(path) as fh:
                return json.load(fh)
        except Exception:
            return None
    return None


def _write_cache(key: str, data: Any) -> None:
    try:
        with open(_cache_path(key), "w") as fh:
            json.dump(data, fh)
    except Exception:
        pass


def _request(path: str, params: dict) -> Optional[dict]:
    query = urllib.parse.urlencode(params)
    url = f"{API_BASE}/{path}?{query}"
    headers = {}
    api_key = os.environ.get("POKEMONTCG_API_KEY")
    if api_key:
        headers["X-Api-Key"] = api_key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def search_cards(query: str = "", page: int = 1, page_size: int = 24,
                 standard_only: bool = True) -> dict:
    """Search the official card database. Cached per query/page."""
    q_parts = []
    if query:
        q_parts.append(f'name:"{query}*"')
    if standard_only:
        q_parts.append("legalities.standard:legal")
    q = " ".join(q_parts) if q_parts else "legalities.standard:legal"
    cache_key = f"search::{q}::{page}::{page_size}"
    cached = _read_cache(cache_key)
    if cached is not None:
        return {**cached, "source": "cache"}

    data = _request("cards", {
        "q": q, "page": page, "pageSize": page_size,
        "orderBy": "-set.releaseDate",
    })
    if data is None:
        return {"data": _fallback_cards(query), "source": "fallback", "totalCount": 0}

    cards = [_slim(c) for c in data.get("data", [])]
    result = {"data": cards, "totalCount": data.get("totalCount", len(cards)), "page": page}
    _write_cache(cache_key, result)
    return {**result, "source": "api"}


def _slim(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "supertype": c.get("supertype"),
        "subtypes": c.get("subtypes", []),
        "hp": c.get("hp"),
        "types": c.get("types", []),
        "image": (c.get("images") or {}).get("small"),
        "image_large": (c.get("images") or {}).get("large"),
        "set": (c.get("set") or {}).get("name"),
        "rarity": c.get("rarity"),
        "number": c.get("number"),
    }


def _fallback_cards(query: str) -> list[dict]:
    from .cards_db import CATALOG, set_name
    out = []
    for cd in CATALOG.values():
        if query and query.lower() not in cd.name.lower():
            continue
        out.append({
            "id": cd.id, "name": cd.name, "supertype": cd.category.value,
            "hp": cd.hp or None, "types": [t.value for t in cd.types],
            "image": cd.image or None, "set": set_name(cd.id) or cd.set_code,
            "battle_ready": True,
        })
    return out


def list_standard_sets() -> dict:
    cache_key = "sets::standard"
    cached = _read_cache(cache_key)
    if cached is not None:
        return {**cached, "source": "cache"}
    data = _request("sets", {"q": "legalities.standard:legal", "orderBy": "-releaseDate"})
    if data is None:
        return {"data": [], "source": "fallback"}
    sets = [{"id": s.get("id"), "name": s.get("name"),
             "releaseDate": s.get("releaseDate"),
             "total": s.get("total")} for s in data.get("data", [])]
    result = {"data": sets}
    _write_cache(cache_key, result)
    return {**result, "source": "api"}
