"""Decklist import.

Parses a pasted decklist (the common Pokémon TCG Live export format, or a plain
``<count> <card name>`` per line) and maps each entry onto the engine's
*implemented* cards in ``cards_db.CATALOG``. Cards the engine doesn't yet
implement are reported as ``unknown`` rather than silently dropped, so the user
knows exactly why a list isn't battle-ready.

Example input::

    Pokémon: 9
    3 Charizard ex OBF 125
    2 Charmeleon MEW 27
    4 Charmander MEW 26
    ...
    Trainer: 15
    4 Professor's Research SVI 189
    ...
    Energy: 36
    29 Basic Fire Energy SVE 10
    7 Double Turbo Energy BRS 151
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from engine.cards import CardDef
from .cards_db import CATALOG

# Section headers like "Pokémon: 9", "Trainer:", "Energy: 36".
_SECTION = re.compile(r"^\s*(pok[eé]mon|trainer|energy)\s*:?\s*\d*\s*$", re.IGNORECASE)
# A card line: "<count> <name> [SET NUMBER]".
_LINE = re.compile(r"^\s*(\d+)\s*[xX]?\s+(.+?)\s*$")
# Trailing "<SET> <NUMBER>" token (e.g. "OBF 125", "SVI 189", "SVE 10").
_TRAILING_SET = re.compile(r"\s+[A-Z][A-Z0-9]{1,4}\s+[A-Za-z0-9]+\s*$")

# Build a normalised name -> CardDef index once.
_BY_NAME: dict[str, CardDef] = {c.name.lower(): c for c in CATALOG.values()}


def _normalise_name(raw: str) -> str:
    name = _TRAILING_SET.sub("", raw).strip()
    # PTCGL prefixes basic energy with "Basic " ("Basic Fire Energy").
    if name.lower().startswith("basic ") and name.lower().endswith("energy"):
        name = name[len("Basic "):]
    return name.strip()


@dataclass
class ParsedDeck:
    cards: list[CardDef] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    unknown: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cards)

    @property
    def ok(self) -> bool:
        # Warnings (e.g. the 4-copy guideline) don't block import; errors and
        # unimplemented cards do.
        return not self.errors and not self.unknown


def parse_decklist(text: str) -> ParsedDeck:
    out = ParsedDeck()
    if not text or not text.strip():
        out.errors.append("Decklist is empty.")
        return out

    for line in text.splitlines():
        line = line.strip()
        if not line or _SECTION.match(line):
            continue
        m = _LINE.match(line)
        if not m:
            out.errors.append(f"Could not parse line: {line!r}")
            continue
        count = int(m.group(1))
        name = _normalise_name(m.group(2))
        card = _BY_NAME.get(name.lower())
        if card is None:
            out.unknown.append(f"{count} {name}")
            continue
        out.counts[card.name] = out.counts.get(card.name, 0) + count
        out.cards.extend([card] * count)

    _validate(out)
    return out


def _validate(d: ParsedDeck) -> None:
    if d.total != 60 and not d.unknown:
        d.errors.append(f"Deck has {d.total} cards; Standard requires exactly 60.")
    if not any(c.is_basic_pokemon for c in d.cards):
        d.errors.append("Deck has no Basic Pokémon — it could never start a game.")
    # 4-copy rule (basic energy is exempt). A guideline, not a hard block:
    # the engine doesn't enforce deck-building legality, so surface it as a
    # warning rather than rejecting the import.
    for name, n in d.counts.items():
        card = _BY_NAME.get(name.lower())
        if card and not card.is_basic_energy and n > 4:
            d.warnings.append(f"{name}: {n} copies exceeds the usual 4-copy limit.")


def render_decklist(spec: list[tuple[CardDef, int]]) -> str:
    """Render a (card, count) spec as an importable decklist string."""
    pk = [(c, n) for c, n in spec if c.is_pokemon]
    tr = [(c, n) for c, n in spec if c.is_trainer]
    en = [(c, n) for c, n in spec if c.is_energy]
    lines: list[str] = []
    for label, group in (("Pokémon", pk), ("Trainer", tr), ("Energy", en)):
        if not group:
            continue
        lines.append(f"{label}: {sum(n for _, n in group)}")
        for c, n in group:
            nm = f"Basic {c.name}" if c.is_basic_energy else c.name
            lines.append(f"{n} {nm}")
        lines.append("")
    return "\n".join(lines).strip()


def battle_ready_cards() -> list[dict]:
    """Names the importer will recognise, for the UI to surface."""
    out = []
    for c in CATALOG.values():
        out.append({
            "name": c.name,
            "category": c.category.value,
            "hp": c.hp or None,
            "types": [t.value for t in c.types],
            "is_basic": c.is_basic_pokemon,
        })
    return sorted(out, key=lambda x: (x["category"], x["name"]))
