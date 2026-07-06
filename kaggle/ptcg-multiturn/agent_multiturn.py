"""PTCG AI Battle Challenge - Simulation entrypoint (main.py).

A compact, card-aware heuristic agent for the official `cg` engine. It is:

  * SCHEMA-CORRECT - it parses the real `cg` Observation (select / option /
    current State), not a guessed `legal_actions` list.
  * CARD-AWARE - it reads HP, types, weakness, and attack costs/damage from the
    engine's own card database (`cg.api.all_card_data` / `all_attack`), so it can
    recognise lethal, power up the right attacker, and develop the board.
  * OFFLINE + FAST - no network, no ML weights, O(options) per decision, so it
    never approaches the per-match time limit (running out the clock = a loss).
  * ROBUST - every decision is wrapped so that on any unexpected input it still
    returns a *legal* selection instead of crashing (a crash forfeits the game).

Turn logic (main phase), highest priority first:
  1. take a lethal attack if one exists;
  2. otherwise develop: evolve -> attach energy to the attacker -> play
     draw/search & bench basics -> use abilities;
  3. when no development remains, attack for the most (effective) damage;
  4. only end the turn when nothing else helps.

Sub-selections (targets, discards, coin flips, mulligan, first/second, ...) are
resolved by context with sensible defaults and a safe legal fallback.
"""
import os
# Provable offline guarantee (belt-and-braces; this agent never networks anyway).
os.environ.setdefault("PTCG_OFFLINE", "1")

import csv
import random
import time
from collections import Counter

from cg.api import (
    Observation, to_observation_class,
    OptionType, SelectType, SelectContext, AreaType,
)

# Optional forward-search API (present in the competition engine). If it is not
# importable the agent silently falls back to the pure heuristic below.
try:
    from cg.api import search_begin, search_step, search_end
    _HAS_SEARCH = True
except Exception:  # pragma: no cover
    _HAS_SEARCH = False

random.seed(0)

# --------------------------------------------------------------------------- #
# Card knowledge (built once at import).
# --------------------------------------------------------------------------- #
try:
    from cg.api import all_card_data, all_attack
    _CARDS = {c.cardId: c for c in all_card_data()}
    _ATTACKS = {a.attackId: a for a in all_attack()}
except Exception:  # pragma: no cover - engine always present in competition
    _CARDS, _ATTACKS = {}, {}

_MAX_BELT_ID = 1158  # ACE SPEC tool: +50 damage vs the opponent's ex


def _card(cid):
    return _CARDS.get(cid)


def _is_basic_pokemon(cid):
    c = _card(cid)
    return bool(c) and int(getattr(c, "cardType", -1)) == 0 and bool(getattr(c, "basic", False))


def _poke_value(pkmn):
    """Rough 'how good an attacker is this' score: best printed attack damage
    (with a small HP tie-break)."""
    if pkmn is None:
        return -1.0
    c = _card(getattr(pkmn, "id", None))
    best = 0
    if c:
        for aid in getattr(c, "attacks", []) or []:
            a = _ATTACKS.get(aid)
            if a and a.damage > best:
                best = a.damage
    return best + 0.01 * (getattr(pkmn, "hp", 0) or 0)


# --------------------------------------------------------------------------- #
# Deck loading (60 bare card-IDs, one per line - the format the engine reads).
# --------------------------------------------------------------------------- #
def read_deck_csv():
    path = "deck.csv"
    if not os.path.exists(path):
        path = "/kaggle_simulations/agent/deck.csv"
    ids = []
    with open(path, "r", encoding="utf-8") as fh:
        for row in fh.read().splitlines():
            row = row.strip()
            if not row or row.startswith("#"):
                continue
            try:
                ids.append(int(row.split(",")[0]))
            except ValueError:
                continue
    return ids[:60]


# --------------------------------------------------------------------------- #
# State accessors.
# --------------------------------------------------------------------------- #
def _me(state):
    return state.yourIndex


def _active(state, player):
    arr = state.players[player].active
    return arr[0] if arr else None


def _opt_pokemon(state, opt):
    """The Pokemon a CARD-type option points at (ACTIVE/BENCH), else None."""
    try:
        pi = opt.playerIndex if opt.playerIndex is not None else _me(state)
        ps = state.players[pi]
        if opt.area == AreaType.ACTIVE:
            return ps.active[opt.index] if ps.active else None
        if opt.area == AreaType.BENCH:
            return ps.bench[opt.index]
    except Exception:
        pass
    return None


def _opt_card_id(state, opt):
    """The card-id a hand/discard/deck option points at, if resolvable."""
    try:
        if opt.cardId:
            return opt.cardId
        pi = opt.playerIndex if opt.playerIndex is not None else _me(state)
        ps = state.players[pi]
        area = opt.area
        if area == AreaType.HAND and ps.hand:
            return ps.hand[opt.index].id
        if area == AreaType.DISCARD:
            return ps.discard[opt.index].id
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------- #
# Damage / lethal estimation.
# --------------------------------------------------------------------------- #
def _effective_damage(attack_id, attacker, defender):
    a = _ATTACKS.get(attack_id)
    if not a or attacker is None or defender is None:
        return 0
    dmg = a.damage
    if dmg <= 0:
        return 0  # variable/effect attacks: don't over-claim
    atk_card = _card(getattr(attacker, "id", None))
    def_card = _card(getattr(defender, "id", None))
    # Weakness (Scarlet & Violet: x2); Resistance (-30).
    if atk_card and def_card:
        if def_card.weakness is not None and int(def_card.weakness) == int(atk_card.energyType):
            dmg *= 2
        if def_card.resistance is not None and int(def_card.resistance) == int(atk_card.energyType):
            dmg = max(0, dmg - 30)
        # Maximum Belt: +50 vs an ex, if attached to our attacker.
        if getattr(def_card, "ex", False):
            for t in getattr(attacker, "tools", []) or []:
                if t.id == _MAX_BELT_ID:
                    dmg += 50
                    break
    return dmg


def _best_attack(state, options):
    """(best_index, best_damage, lethal_index) over ATTACK options in `options`."""
    me = _me(state)
    attacker = _active(state, me)
    defender = _active(state, 1 - me)
    def_hp = getattr(defender, "hp", 10 ** 9) if defender else 10 ** 9
    best_i, best_dmg, lethal_i = -1, -1, -1
    for i, o in enumerate(options):
        if o.type != OptionType.ATTACK:
            continue
        d = _effective_damage(o.attackId, attacker, defender)
        if d > best_dmg:
            best_i, best_dmg = i, d
        if d >= def_hp and lethal_i < 0:
            lethal_i = i
    return best_i, best_dmg, lethal_i


# --------------------------------------------------------------------------- #
# Main-phase priority.
# --------------------------------------------------------------------------- #
def _play_value(state, opt):
    """Priority for a PLAY option (which card from hand to play)."""
    cid = _opt_card_id(state, opt)
    c = _card(cid)
    if not c:
        return 1.0
    t = int(c.cardType)
    if t == 3:          # SUPPORTER (draw / search) - strong, once per turn
        return 5.0
    if t == 1:          # ITEM (ball / recovery)
        return 4.0
    if t == 0:          # POKEMON - develop the bench
        return 4.5 if c.basic else 2.0
    if t == 4:          # STADIUM
        return 2.5
    return 1.5


def _decide_main(state, sel):
    options = sel.option
    # 1. Lethal now?
    _, _, lethal_i = _best_attack(state, options)
    if lethal_i >= 0:
        return [lethal_i]

    # 2. Development, in priority order.
    idx = {OptionType.EVOLVE: [], OptionType.ATTACH: [], OptionType.PLAY: [],
           OptionType.ABILITY: []}
    for i, o in enumerate(options):
        if o.type in idx:
            idx[o.type].append(i)

    if idx[OptionType.EVOLVE]:                       # evolve toward the ace
        return [idx[OptionType.EVOLVE][0]]
    if idx[OptionType.ATTACH]:                       # attach energy to attacker
        me = _me(state)
        pref = None
        for i in idx[OptionType.ATTACH]:
            o = options[i]
            if o.inPlayArea == AreaType.ACTIVE or o.index == 0:
                pref = i
                break
        return [pref if pref is not None else idx[OptionType.ATTACH][0]]
    if idx[OptionType.PLAY]:                          # dig / develop bench
        best = max(idx[OptionType.PLAY], key=lambda i: _play_value(state, options[i]))
        return [best]
    if idx[OptionType.ABILITY]:                       # use an ability
        return [idx[OptionType.ABILITY][0]]

    # 3. No development left - attack for the most damage if it does anything.
    best_i, best_dmg, _ = _best_attack(state, options)
    if best_i >= 0 and best_dmg > 0:
        return [best_i]

    # 4. Otherwise end the turn.
    for i, o in enumerate(options):
        if o.type == OptionType.END:
            return [i]
    return _safe(sel)


# --------------------------------------------------------------------------- #
# Sub-selection handling (targets, yes/no, counts, discards, ...).
# --------------------------------------------------------------------------- #
def _yesno_index(options, want_yes):
    want = OptionType.YES if want_yes else OptionType.NO
    for i, o in enumerate(options):
        if o.type == want:
            return i
    return 0


def _topk_by(options, key, k, reverse=True):
    order = sorted(range(len(options)), key=key, reverse=reverse)
    k = max(0, min(k, len(order)))
    return sorted(order[:k])


def _card_grab_value(state, opt):
    """Value of a card to ADD to hand (search targets): Pokemon > energy > rest."""
    c = _card(_opt_card_id(state, opt))
    if not c:
        return 1.0
    t = int(c.cardType)
    if t == 0:
        return 6.0 if (c.ex or c.stage2 or c.stage1) else 5.0
    if t in (5, 6):     # energy
        return 3.0
    return 2.0          # trainers


def _decide_sub(state, sel):
    ctx = sel.context
    options = sel.option
    lo, hi = sel.minCount, sel.maxCount
    me = _me(state)

    # -- Yes / No prompts ---------------------------------------------------- #
    if sel.type == SelectType.YES_NO:
        if ctx == SelectContext.IS_FIRST:
            return [_yesno_index(options, want_yes=False)]      # go second
        if ctx == SelectContext.MULLIGAN:
            hand = state.players[me].hand or []
            keep = any(_is_basic_pokemon(c.id) for c in hand)
            return [_yesno_index(options, want_yes=not keep)]   # keep if we can
        # Coin, activate-effect, devolve-more, etc.: take the effect.
        return [_yesno_index(options, want_yes=True)]

    # -- Choosing an attack -------------------------------------------------- #
    if sel.type == SelectType.ATTACK or ctx == SelectContext.ATTACK:
        best_i, best_dmg, lethal_i = _best_attack(state, options)
        pick = lethal_i if lethal_i >= 0 else best_i
        return [pick if pick >= 0 else 0]

    # -- Counts (draw how many / place how many counters) -------------------- #
    if sel.type == SelectType.COUNT:
        cost_like = ctx in (SelectContext.DISCARD, SelectContext.TO_DECK,
                            SelectContext.TO_DECK_BOTTOM)
        key = (lambda i: (options[i].number or 0))
        idx = min(range(len(options)), key=key) if cost_like else max(range(len(options)), key=key)
        return [idx]

    # -- Promote / put a Pokemon into play: best attacker -------------------- #
    if ctx in (SelectContext.SETUP_ACTIVE_POKEMON, SelectContext.TO_ACTIVE,
               SelectContext.TO_FIELD, SelectContext.SWITCH, SelectContext.EVOLVES_TO):
        return _topk_by(options, lambda i: _opt_attacker_value(state, options[i]),
                        max(lo, 1))

    # -- Bench Pokemon: develop as many as allowed --------------------------- #
    if ctx in (SelectContext.SETUP_BENCH_POKEMON, SelectContext.TO_BENCH):
        return _topk_by(options, lambda i: _opt_attacker_value(state, options[i]),
                        hi if hi else lo)

    # -- Search-to-hand: grab the most useful cards -------------------------- #
    if ctx in (SelectContext.TO_HAND, SelectContext.TO_HAND_ENERGY):
        return _topk_by(options, lambda i: _card_grab_value(state, options[i]), max(lo, 1))

    # -- Discards / send to deck: shed the least useful ---------------------- #
    if ctx in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD,
               SelectContext.DISCARD_ENERGY, SelectContext.DISCARD_ENERGY_CARD,
               SelectContext.TO_DECK, SelectContext.TO_DECK_BOTTOM,
               SelectContext.TO_DECK_ENERGY):
        k = lo if lo else 0
        if k == 0:
            return []
        return _topk_by(options, lambda i: _card_grab_value(state, options[i]), k, reverse=False)

    # -- Heal / remove damage from OUR most hurt Pokemon --------------------- #
    if ctx in (SelectContext.HEAL, SelectContext.REMOVE_DAMAGE_COUNTER):
        def hurt(i):
            p = _opt_pokemon(state, options[i])
            if not p or not getattr(p, "maxHp", 0):
                return 0.0
            return 1.0 - (p.hp / p.maxHp)
        return _topk_by(options, hurt, max(lo, 1))

    # -- Place damage / deal damage: hit the opponent's weakest -------------- #
    if ctx in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER,
               SelectContext.DAMAGE_COUNTER_ANY):
        def target(i):
            o = options[i]
            p = _opt_pokemon(state, o)
            opp = (o.playerIndex is not None and o.playerIndex != me)
            hp = getattr(p, "hp", 9999) if p else 9999
            # prefer opponent Pokemon (higher score), and among them the lowest HP
            return (1 if opp else 0) * 100000 - hp
        return _topk_by(options, target, max(lo, 1))

    # -- Attach energy / apply effect to OUR attacker ------------------------ #
    if ctx in (SelectContext.ATTACH_FROM, SelectContext.ATTACH_TO,
               SelectContext.EFFECT_TARGET):
        # Prefer the active Pokemon; else our best bench attacker.
        for i, o in enumerate(options):
            if o.area == AreaType.ACTIVE:
                return [i]
        return _topk_by(options, lambda i: _opt_attacker_value(state, options[i]),
                        max(lo, 1))

    # -- Everything else: safe, legal default ------------------------------- #
    return _safe(sel)


# --------------------------------------------------------------------------- #
# Safe fallback + dispatch.
# --------------------------------------------------------------------------- #
def _safe(sel):
    """A guaranteed-legal selection: the first `minCount` option indices
    (or nothing, when zero selections are allowed)."""
    lo = max(0, sel.minCount)
    n = len(sel.option)
    if lo == 0:
        return []
    return list(range(min(lo, n)))



def _opt_attacker_value(state, opt):
    """Attacker quality for an option that may reference an in-play Pokemon OR a
    hand card (setup/bench choices reference the hand)."""
    p = _opt_pokemon(state, opt)
    if p is not None:
        return _poke_value(p)
    c = _card(_opt_card_id(state, opt))
    if not c:
        return 0.0
    best = 0
    for aid in getattr(c, "attacks", []) or []:
        a = _ATTACKS.get(aid)
        if a and a.damage > best:
            best = a.damage
    return best + 0.01 * (getattr(c, "hp", 0) or 0)


def _decide(obs):
    sel = obs.select
    if sel is None:               # initial deck selection
        return read_deck_csv()
    if not sel.option:            # nothing to choose
        return _safe(sel)
    if sel.type == SelectType.MAIN or sel.context == SelectContext.MAIN:
        return _decide_main(obs.current, sel)
    return _decide_sub(obs.current, sel)


# =========================================================================== #
# Forward-search layer.
#
# The engine ships its own forward simulator (`search_begin/step/end`). Rather
# than follow a fixed action checklist, on each MAIN decision we try *every*
# first action, play the rest of the turn out with the heuristic as a rollout
# policy, and keep the first action whose end-of-turn board scores best under a
# value function (prizes taken, damage dealt, energy attached, board width).
#
# Why this is tractable: during our own turn the opponent never acts, so we only
# need to seed OUR hidden cards accurately (our decklist minus everything we can
# see); the opponent's hidden zones just need legal filler. Every step is
# wrapped so that on any failure we fall back to the pure heuristic - search can
# only ever *improve* on it, never break it.
# =========================================================================== #
_USE_SEARCH = True
_STEP_BUDGET = 4000    # raised for multi-turn: opponent-turn sims cost many steps
_ROLLOUT_STEPS = 60    # max steps to finish one turn rollout
_MAX_BRANCH = 12       # max distinct first-actions to evaluate
_BRANCH2 = 5           # branching at the 2nd ply
_SEARCH_DEPTH = 2      # MAIN plies to branch before greedy rollout
_TIME_BUDGET = 2.5     # raised for multi-turn depth; still well under Kaggle limits

# Anti-stall: no legitimate turn needs anywhere near this many MAIN actions, so
# if we ever exceed it we force END. This can't affect normal play; it only
# breaks a degenerate intra-turn loop that would otherwise run out the clock.
_TURN_ACTION_CAP = 40
_turn_guard = {"turn": None, "n": 0}

# --------------------------------------------------------------------------- #
# MULTI-TURN LOOKAHEAD (experimental scaffolding).
#
# The single-turn search evaluates the board at the end of OUR turn. That misses
# the whole point of setup-heavy decks, whose investment only pays off on later
# turns. Here we extend the horizon: after our turn ends we SIMULATE the
# opponent's turn (and optionally our next turn) before evaluating, so lines that
# leave us better-positioned *after the opponent responds* score higher.
#
# HIDDEN-INFORMATION CAVEAT (important): during our own turn the opponent never
# acts, so the single-turn search only needs OUR hidden cards seeded correctly.
# To simulate the opponent's turn we must act for them — but their hand and deck
# are hidden, so `_seed_hidden` fills those zones with *legal filler*, not their
# real cards. Their VISIBLE board (active/bench/attached energy) is accurate, so
# their attacks with already-in-play Pokemon are realistic; their draws and
# hand-plays are only approximate. Treat multi-turn values as a better-but-noisy
# estimate, and see the README for ways to sharpen the opponent model.
#
#   _MULTITURN_HORIZON = 0  -> single-turn (identical to the shipped agent)
#                        1  -> our turn + opponent's response  (2-ply)
#                        2  -> ... + our next turn              (3-ply)
# The opponent is played by our own heuristic from their perspective (`_decide`
# keys off state.yourIndex, so it naturally plays for whoever is to move).
_MULTITURN_HORIZON = 1
_OPP_TURN_STEPS = 400   # hard cap on sim steps spent driving one opponent turn

# Opponent model used when simulating their turn:
#   "heuristic" - drive their FULL turn with our heuristic. Accurate for their
#                 in-play attacks but plays their (fake, seeded) hand too, which
#                 adds noise.
#   "threat"    - they only attach one energy (engine-enforced max) and attack
#                 with their best in-play attacker, then end. Uses ONLY their real
#                 visible board, so it sidesteps the hidden-hand noise entirely.
#                 This is the "what's the worst they do to me this turn" model.
_OPP_MODEL = "threat"

# Selective lookahead: only pay for the opponent simulation on turns where our
# active is actually in danger (the opponent's best visible attack can KO it).
# On safe turns we fall back to the single-turn evaluation, preserving search
# breadth where depth wouldn't change the decision anyway. This targets the one
# question multi-turn answers well ("does my board survive?") and avoids diluting
# every other turn. Set False to look ahead on every turn.
_SELECTIVE = True


def _find_filler_ids():
    """A valid Basic-Pokemon id and Basic-Energy id, for seeding zones whose
    exact contents don't affect our own-turn rollout."""
    bp = be = None
    for cid, c in _CARDS.items():
        ct = int(getattr(c, "cardType", -1))
        if bp is None and ct == 0 and getattr(c, "basic", False):
            bp = cid
        if be is None and ct == 5:  # BASIC_ENERGY
            be = cid
        if bp and be:
            break
    return (bp or 1), (be or 1)


_FILLER_POKE, _FILLER_ENERGY = _find_filler_ids()

_DECK_CACHE = None


def _my_deck_list():
    global _DECK_CACHE
    if _DECK_CACHE is None:
        _DECK_CACHE = read_deck_csv()
    return _DECK_CACHE


def _visible_my_cards(state, me):
    """Multiset (as a list) of every one of our card-ids currently visible to
    us: hand, board Pokemon + their attached energy/tools/pre-evos, discard,
    and our stadium. The complement within our decklist is deck+prizes."""
    seen = []
    ps = state.players[me]

    def add_card(c):
        if c is not None and getattr(c, "id", None) is not None:
            seen.append(c.id)

    def add_poke(p):
        if p is None:
            return
        if getattr(p, "id", None) is not None:
            seen.append(p.id)
        for e in getattr(p, "energyCards", []) or []:
            add_card(e)
        for t in getattr(p, "tools", []) or []:
            add_card(t)
        for pe in getattr(p, "preEvolution", []) or []:
            add_card(pe)

    for p in (ps.active or []):
        add_poke(p)
    for p in ps.bench:
        add_poke(p)
    for c in ps.discard:
        add_card(c)
    for c in (ps.hand or []):
        add_card(c)
    for c in (state.stadium or []):
        if getattr(c, "playerIndex", me) == me:
            add_card(c)
    return seen


def _seed_hidden(obs):
    """Build the (your_deck, your_prize, opp_deck, opp_prize, opp_hand,
    opp_active) prediction that `search_begin` requires."""
    state = obs.current
    me = state.yourIndex
    opp = 1 - me
    mp = state.players[me]
    op = state.players[opp]

    # -- our unseen cards -> deck + prize (identities we actually try to get right)
    deck_n = mp.deckCount
    prize_n = len(mp.prize)
    unseen = Counter(_my_deck_list()) - Counter(_visible_my_cards(state, me))
    pool = list(unseen.elements())
    need = deck_n + prize_n
    if len(pool) < need:
        pool += [_FILLER_ENERGY] * (need - len(pool))
    your_prize = pool[:prize_n]
    your_deck = pool[prize_n:prize_n + deck_n]
    if len(your_deck) < deck_n:
        your_deck += [_FILLER_ENERGY] * (deck_n - len(your_deck))
    if len(your_prize) < prize_n:
        your_prize += [_FILLER_ENERGY] * (prize_n - len(your_prize))

    # -- opponent hidden zones: legal filler (they don't move on our turn)
    o_deck_n = op.deckCount
    opp_deck = ([_FILLER_POKE] + [_FILLER_ENERGY] * max(0, o_deck_n - 1)) if o_deck_n else []
    opp_prize = [_FILLER_ENERGY] * len(op.prize)
    opp_hand = [_FILLER_ENERGY] * op.handCount
    oa = op.active
    opp_active = [_FILLER_POKE] if (oa and len(oa) > 0 and oa[0] is None) else []
    return your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active


def _legalize(picks, sel):
    """Coerce a pick list into a guaranteed-legal selection for `sel`."""
    n = len(sel.option)
    out = [i for i in dict.fromkeys(picks) if 0 <= i < n]
    if len(out) < sel.minCount:
        for i in range(n):
            if i not in out:
                out.append(i)
            if len(out) >= sel.minCount:
                break
    if len(out) > sel.maxCount:
        out = out[:sel.maxCount]
    return out


def _best_ready_damage(attacker, defender):
    """Best effective damage `attacker` could do to `defender` RIGHT NOW, i.e.
    with an attack whose energy requirement its current energy plausibly meets
    (approximated by energy count). Used to score KO threats."""
    if attacker is None or defender is None:
        return 0
    c = _card(getattr(attacker, "id", None))
    if not c:
        return 0
    have = len(getattr(attacker, "energies", []) or [])
    best = 0
    for aid in getattr(c, "attacks", []) or []:
        a = _ATTACKS.get(aid)
        if not a:
            continue
        if len(getattr(a, "energies", []) or []) > have:
            continue  # not enough energy attached to use it
        d = _effective_damage(aid, attacker, defender)
        if d > best:
            best = d
    return best


def _eval(state, me):
    """Value of a board from our perspective (higher = better). Evaluated at the
    end of our turn, so the dominant signals are prizes taken this turn, damage
    placed, and whether we now THREATEN a knockout next turn."""
    if state is None:
        return 0.0
    res = getattr(state, "result", -1)
    if res is not None and res >= 0:
        if res == me:
            return 1e6
        if res == (1 - me):
            return -1e6
        return 0.0  # draw
    opp = 1 - me
    mp = state.players[me]
    op = state.players[opp]
    score = 0.0
    # Prize race (the win condition): our pile low & their pile high are both good.
    score += (len(op.prize) - len(mp.prize)) * 1000.0

    oa = op.active[0] if op.active else None
    ma = mp.active[0] if ma_active(mp) else None

    # Damage placed on their active (progress to a KO) vs damage taken on ours.
    if oa is not None:
        score += (getattr(oa, "maxHp", 0) - getattr(oa, "hp", 0)) * 2.0
        if getattr(oa, "hp", 1) <= 0:
            score += 300.0
        # Do we now threaten to KO their active next turn? Strong incentive.
        threat = _best_ready_damage(ma, oa)
        if threat >= getattr(oa, "hp", 10 ** 9):
            score += 250.0
        else:
            score += min(threat, getattr(oa, "hp", 0)) * 1.0
    if ma is not None:
        score -= (getattr(ma, "maxHp", 0) - getattr(ma, "hp", 0)) * 1.0
        score += len(getattr(ma, "energies", []) or []) * 12.0  # energy on attacker
        score += _poke_value(ma) * 2.0
        # Status on our own active is bad (can't act / chip damage / coin-flip risk).
        for flag, pen in (("asleep", 40), ("paralyzed", 40), ("confused", 25),
                          ("poisoned", 20), ("burned", 15)):
            if getattr(mp, flag, False):
                score -= pen
        # Weakness exposure: our active weak to their active's type.
        if oa is not None:
            mc, oc = _card(ma.id), _card(oa.id)
            if mc and oc and mc.weakness is not None and \
                    int(mc.weakness) == int(getattr(oc, "energyType", -999)):
                score -= 30.0

    # A benched attacker ready to promote (insurance against losing the active).
    bench_best = 0.0
    for p in mp.bench:
        bench_best = max(bench_best, _poke_value(p))
    score += bench_best * 1.0

    # Board development and resources.
    score += len(mp.bench) * 20.0
    score += mp.handCount * 3.0
    score -= len(op.bench) * 5.0
    return score


def ma_active(ps):
    return bool(ps.active) and ps.active[0] is not None


def _is_main_sel(sel):
    return sel.type == SelectType.MAIN or sel.context == SelectContext.MAIN


def _opp_threat_policy(state, sel):
    """Opponent policy that models only their real in-play threat: attack with the
    best attacker if able, else attach one energy toward it, else end. Plays no
    cards from their (hidden/filler) hand, so it never acts on fake information."""
    if not _is_main_sel(sel):
        return _decide_sub(state, sel)   # resolve targets/coins normally
    opts = sel.option
    best_i, best_dmg, lethal_i = _best_attack(state, opts)
    if lethal_i >= 0:
        return [lethal_i]
    if best_i >= 0 and best_dmg > 0:
        return [best_i]                  # swing with the best real attack
    # can't attack yet: attach one energy (engine caps this at one per turn)
    for i, o in enumerate(opts):
        if o.type == OptionType.ATTACH and (o.inPlayArea == AreaType.ACTIVE or o.index == 0):
            return [i]
    for i, o in enumerate(opts):
        if o.type == OptionType.ATTACH:
            return [i]
    for i, o in enumerate(opts):
        if o.type == OptionType.END:
            return [i]
    return _safe(sel)


def _opponent_turn(sid, obs, me, budget):
    """Drive the OPPONENT's turn until control returns to `me`, the game ends, or
    the step/time budget is hit. The policy is chosen by _OPP_MODEL: the full
    heuristic (accurate in-play attacks but plays their fake hand) or the threat
    model (attach-one + attack, using only their real visible board)."""
    steps = _OPP_TURN_STEPS
    while steps > 0:
        st = obs.current
        res = getattr(st, "result", -1) if st is not None else -1
        if res is not None and res >= 0:
            return obs, sid
        sel = obs.select
        if sel is None:
            return obs, sid
        if st is not None and st.yourIndex == me:
            return obs, sid  # control is back with us
        if budget["steps"] <= 0 or time.monotonic() > budget["deadline"]:
            return obs, sid
        if _OPP_MODEL == "threat":
            picks = _legalize(_opp_threat_policy(st, sel), sel)
        else:
            picks = _legalize(_decide(obs), sel)  # _decide acts for st.yourIndex
        try:
            ss = search_step(sid, picks)
        except Exception:
            return obs, sid
        obs = ss.observation
        sid = ss.searchId
        budget["steps"] -= 1
        steps -= 1
    return obs, sid


def _our_turn_rollout(sid, obs, me, budget):
    """Greedily play OUR next turn to its end with the heuristic, then evaluate.
    Used only for horizon >= 2; it does NOT recurse into another opponent turn."""
    steps = _ROLLOUT_STEPS
    while steps > 0:
        st = obs.current
        res = getattr(st, "result", -1) if st is not None else -1
        if res is not None and res >= 0:
            return _eval(st, me)
        sel = obs.select
        if sel is None or (st is not None and st.yourIndex != me):
            return _eval(st, me)
        if budget["steps"] <= 0 or time.monotonic() > budget["deadline"]:
            return _eval(st, me)
        picks = _legalize(_decide(obs), sel)
        try:
            ss = search_step(sid, picks)
        except Exception:
            return _eval(st, me)
        obs = ss.observation
        sid = ss.searchId
        budget["steps"] -= 1
        steps -= 1
    return _eval(obs.current, me)


def _incoming_threat(attacker, defender):
    """Best damage the opponent's `attacker` could deal to our `defender` next
    turn, allowing one energy attach. Uses only real, visible board info."""
    if attacker is None or defender is None:
        return 0
    c = _card(getattr(attacker, "id", None))
    if not c:
        return 0
    budget = len(getattr(attacker, "energies", []) or []) + 1
    best = 0
    for aid in getattr(c, "attacks", []) or []:
        a = _ATTACKS.get(aid)
        if not a or len(getattr(a, "energies", []) or []) > budget:
            continue
        d = _effective_damage(aid, attacker, defender)
        if d > best:
            best = d
    return best


def _turn_end_value(sid, obs, me, budget, horizon):
    """Value at OUR turn end, looking `horizon` turns ahead. horizon 0 = evaluate
    now (single-turn, identical to the shipped agent); horizon >= 1 simulates the
    opponent's response first; horizon >= 2 then plays our next turn too. With
    _SELECTIVE, the opponent simulation is skipped on turns where our active is
    not in KO range (depth wouldn't change the decision there)."""
    st = obs.current
    res = getattr(st, "result", -1) if st is not None else -1
    if (res is not None and res >= 0) or horizon <= 0:
        return _eval(st, me)
    if _SELECTIVE and st is not None:
        my_active = st.players[me].active[0] if st.players[me].active else None
        opp_active = st.players[1 - me].active[0] if st.players[1 - me].active else None
        if my_active is not None and \
                _incoming_threat(opp_active, my_active) < getattr(my_active, "hp", 10 ** 9):
            return _eval(st, me)  # we're safe this turn -> single-turn eval
    obs2, sid2 = _opponent_turn(sid, obs, me, budget)
    st2 = obs2.current
    res2 = getattr(st2, "result", -1) if st2 is not None else -1
    if (res2 is not None and res2 >= 0) or horizon <= 1:
        return _eval(st2, me)
    return _our_turn_rollout(sid2, obs2, me, budget)


def _rollout(search_id, obs, me, budget):
    """Finish the current turn greedily with the heuristic, then evaluate."""
    steps = _ROLLOUT_STEPS
    while steps > 0:
        st = obs.current
        res = getattr(st, "result", -1) if st is not None else -1
        if res is not None and res >= 0:
            return _eval(st, me)
        sel = obs.select
        if sel is None:
            return _eval(st, me)
        if st is not None and st.yourIndex != me:
            # our turn is over -> look ahead through the opponent's response
            return _turn_end_value(search_id, obs, me, budget, _MULTITURN_HORIZON)
        if budget["steps"] <= 0 or time.monotonic() > budget["deadline"]:
            return _eval(st, me)
        picks = _decide_main(st, sel) if _is_main_sel(sel) else _decide_sub(st, sel)
        picks = _legalize(picks, sel)
        try:
            ss = search_step(search_id, picks)
        except Exception:
            return _eval(st, me)
        obs = ss.observation
        search_id = ss.searchId
        budget["steps"] -= 1
        steps -= 1
    return _eval(obs.current, me)


def _search_value(sid, obs, me, budget, depth):
    """Best end-of-turn value reachable from this state, branching on up to
    `depth` further MAIN decisions and finishing each line with a greedy
    rollout. Non-MAIN decisions are advanced with the heuristic (no branching)."""
    st = obs.current
    res = getattr(st, "result", -1) if st is not None else -1
    if res is not None and res >= 0:
        return _eval(st, me)
    sel = obs.select
    if sel is None or (st is not None and st.yourIndex != me):
        return _turn_end_value(sid, obs, me, budget, _MULTITURN_HORIZON)
    if depth <= 0 or budget["steps"] <= 0 or time.monotonic() > budget["deadline"]:
        return _rollout(sid, obs, me, budget)
    if not _is_main_sel(sel):
        picks = _legalize(_decide_sub(st, sel), sel)
        try:
            ss = search_step(sid, picks)
        except Exception:
            return _eval(st, me)
        budget["steps"] -= 1
        return _search_value(ss.searchId, ss.observation, me, budget, depth)
    best = -1e18
    for oi in _ordered_first_options(st, sel)[:_BRANCH2]:
        if budget["steps"] <= 0 or time.monotonic() > budget["deadline"]:
            break
        try:
            ss = search_step(sid, [oi])
        except Exception:
            continue
        budget["steps"] -= 1
        v = _search_value(ss.searchId, ss.observation, me, budget, depth - 1)
        if v > best:
            best = v
    if best <= -1e17:
        return _rollout(sid, obs, me, budget)
    return best


def _ordered_first_options(state, sel):
    """Candidate first actions, ordered so the search budget is spent on the
    most promising lines first (but every action type is still tried)."""
    options = sel.option
    _, _, lethal = _best_attack(state, options)
    b = {"lethal": [], "evolve": [], "attach": [], "play": [],
         "ability": [], "attack": [], "end": [], "other": []}
    for i, o in enumerate(options):
        if i == lethal:
            b["lethal"].append(i)
            continue
        t = o.type
        if t == OptionType.EVOLVE:
            b["evolve"].append(i)
        elif t == OptionType.ATTACH:
            b["attach"].append(i)
        elif t == OptionType.PLAY:
            b["play"].append(i)
        elif t == OptionType.ABILITY:
            b["ability"].append(i)
        elif t == OptionType.ATTACK:
            b["attack"].append(i)
        elif t == OptionType.END:
            b["end"].append(i)
        else:
            b["other"].append(i)
    b["play"].sort(key=lambda i: _play_value(state, options[i]), reverse=True)
    order = (b["lethal"] + b["evolve"] + b["attach"] + b["play"] +
             b["ability"] + b["attack"] + b["other"] + b["end"])
    return order[:_MAX_BRANCH]


def _search_main(obs):
    """Pick the MAIN action whose heuristic-rollout end-of-turn board is best."""
    if not getattr(obs, "search_begin_input", None):
        raise RuntimeError("no search_begin_input available")
    state = obs.current
    me = state.yourIndex
    root = search_begin(obs, *_seed_hidden(obs))
    try:
        sel = root.observation.select
        cand = _ordered_first_options(state, sel)
        budget = {"steps": _STEP_BUDGET, "deadline": time.monotonic() + _TIME_BUDGET}
        best_i, best_v = None, -1e18
        for oi in cand:
            if budget["steps"] <= 0 or time.monotonic() > budget["deadline"]:
                break
            try:
                child = search_step(root.searchId, [oi])
            except Exception:
                continue
            budget["steps"] -= 1
            v = _search_value(child.searchId, child.observation, me,
                              budget, _SEARCH_DEPTH - 1)
            if v > best_v:
                best_v, best_i = v, oi
        if best_i is None:
            raise RuntimeError("search evaluated no candidate")
        return [best_i]
    finally:
        try:
            search_end()
        except Exception:
            pass


def _choose(obs):
    """Search for MAIN decisions (falling back to the heuristic on any failure);
    heuristic for everything else."""
    sel = obs.select
    if sel is None:
        return read_deck_csv()
    if not sel.option:
        return _safe(sel)
    # Anti-stall guard: count MAIN decisions within the current turn and force
    # END past a high cap, so no degenerate loop can run out the clock.
    if _is_main_sel(sel):
        st = obs.current
        t = getattr(st, "turn", None) if st is not None else None
        if t != _turn_guard["turn"]:
            _turn_guard["turn"] = t
            _turn_guard["n"] = 0
        _turn_guard["n"] += 1
        if _turn_guard["n"] > _TURN_ACTION_CAP:
            for i, o in enumerate(sel.option):
                if o.type == OptionType.END:
                    return [i]
            return _safe(sel)
    if _USE_SEARCH and _HAS_SEARCH and _is_main_sel(sel):
        try:
            picks = _search_main(obs)
            if picks:
                return picks
        except Exception:
            pass
    return _decide(obs)


def agent(obs_dict):
    """Competition entrypoint. Returns a list of chosen option indices
    (or the 60-card deck on the initial call)."""
    try:
        obs = to_observation_class(obs_dict)
        result = _choose(obs)
        # Final legality guard.
        sel = obs.select
        if sel is None:
            return result
        n = len(sel.option)
        result = [i for i in dict.fromkeys(result) if 0 <= i < n]  # unique, in range
        if len(result) < sel.minCount:
            for i in range(n):
                if i not in result:
                    result.append(i)
                if len(result) >= sel.minCount:
                    break
        if len(result) > sel.maxCount:
            result = result[:sel.maxCount]
        return result
    except Exception:
        # Never crash: fall back to a minimal legal move.
        try:
            sel = obs_dict.get("select")
            if not sel:
                return read_deck_csv()
            lo = sel.get("minCount", 1) or 0
            n = len(sel.get("option", []))
            return list(range(min(max(lo, 1), n))) if n else []
        except Exception:
            return [0]


if __name__ == "__main__":
    # Structural smoke test with the real card DB but synthetic observations.
    print("cards loaded:", len(_CARDS), "attacks loaded:", len(_ATTACKS))
    print("deck size:", len(read_deck_csv()))
