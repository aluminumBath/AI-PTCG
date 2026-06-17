"""Rules reference ("rule feed").

A structured, human-readable list of the official Pokémon TCG rules the engine
enforces, grouped by phase. Served at /api/rules and shown in the UI so players
can see exactly which rules are in effect (and where the engine makes a
documented simplification). Keeping this next to the engine makes it a living
checklist for rule fidelity.
"""
from __future__ import annotations

RULES: list[dict] = [
    {
        "group": "Setup",
        "items": [
            {"rule": "Coin flip for first player",
             "detail": "A coin flip decides who takes the first turn."},
            {"rule": "Opening hand needs a Basic",
             "detail": "Draw 7. If you have no Basic Pokémon, reveal and mulligan (reshuffle and redraw) until you do."},
            {"rule": "Place Active + Bench",
             "detail": "Put one Basic Pokémon as your Active and up to 5 on your Bench."},
            {"rule": "Six Prize cards",
             "detail": "Each player sets aside 6 Prize cards face down."},
        ],
    },
    {
        "group": "Turn structure",
        "items": [
            {"rule": "Draw at start of turn",
             "detail": "Begin each turn by drawing a card — including the first player's first turn."},
            {"rule": "First player can't attack on turn 1",
             "detail": "The player going first may not attack during their first turn."},
            {"rule": "First player can't evolve on turn 1",
             "detail": "No evolving during the first player's first turn of the game."},
            {"rule": "One Energy attachment per turn",
             "detail": "Attach at most one Energy from your hand each turn."},
            {"rule": "One Supporter per turn",
             "detail": "You may play at most one Supporter card per turn."},
            {"rule": "One Stadium per turn",
             "detail": "At most one Stadium per turn; a new Stadium replaces the one in play."},
            {"rule": "Attacking ends your turn",
             "detail": "After you attack, your turn ends."},
        ],
    },
    {
        "group": "Evolving & Bench",
        "items": [
            {"rule": "No evolving the turn a Pokémon arrives",
             "detail": "A Pokémon can't evolve the same turn you played or evolved it."},
            {"rule": "Evolution chain order",
             "detail": "Evolve only onto the named pre-evolution (Basic → Stage 1 → Stage 2)."},
            {"rule": "Bench holds five",
             "detail": "You may have at most five Benched Pokémon."},
            {"rule": "Evolving heals conditions",
             "detail": "Evolving removes all Special Conditions and keeps damage and attached cards."},
        ],
    },
    {
        "group": "Attacking & damage",
        "items": [
            {"rule": "Pay the Energy cost",
             "detail": "An attack requires its exact Energy cost; Colorless can be paid by any type."},
            {"rule": "Weakness ×2",
             "detail": "Damage to a Pokémon weak to the attacker's type is doubled."},
            {"rule": "Resistance −30",
             "detail": "Damage to a Pokémon resistant to the attacker's type is reduced by 30."},
            {"rule": "Confusion risk",
             "detail": "A Confused attacker flips a coin; on tails the attack fails and it takes 30 damage."},
        ],
    },
    {
        "group": "Special Conditions (Pokémon Checkup)",
        "items": [
            {"rule": "Conditions sit on the Active Pokémon",
             "detail": "Special Conditions only affect the Active Pokémon and clear when it leaves the Active Spot (retreat, switch, evolve)."},
            {"rule": "Checkup affects both Actives",
             "detail": "Between turns, Poison, Burn and Sleep are resolved on both players' Active Pokémon."},
            {"rule": "Poisoned",
             "detail": "Takes 10 damage at each Checkup."},
            {"rule": "Burned",
             "detail": "Takes 20 damage at each Checkup, then a coin flip; heads removes it."},
            {"rule": "Asleep",
             "detail": "Can't attack or retreat; flip each Checkup, heads wakes it up."},
            {"rule": "Paralyzed",
             "detail": "Can't attack or retreat; recovers during the Checkup after its controller's turn."},
        ],
    },
    {
        "group": "Knockouts & Prizes",
        "items": [
            {"rule": "Knocked Out at full damage",
             "detail": "A Pokémon with damage equal to or above its HP is Knocked Out and discarded with its attached cards."},
            {"rule": "Take a Prize per KO",
             "detail": "Take one Prize card when you Knock Out an opponent's Pokémon."},
            {"rule": "Rule-Box Pokémon give extra Prizes",
             "detail": "Knocking out a Pokémon ex / V gives 2 Prizes; VMAX gives 3."},
            {"rule": "Promote a new Active",
             "detail": "If your Active is Knocked Out, promote a Benched Pokémon to the Active Spot."},
        ],
    },
    {
        "group": "Winning",
        "items": [
            {"rule": "Take all your Prizes",
             "detail": "Take your last Prize card to win."},
            {"rule": "Opponent has no Pokémon",
             "detail": "If your opponent has no Pokémon in play, you win."},
            {"rule": "Opponent can't draw",
             "detail": "If a player can't draw at the start of their turn, they lose (deck-out)."},
        ],
    },
    {
        "group": "Deck construction",
        "items": [
            {"rule": "Exactly 60 cards",
             "detail": "A deck must contain exactly 60 cards."},
            {"rule": "4-copy limit",
             "detail": "At most 4 copies of any card with the same name — except Basic Energy, which is unlimited."},
            {"rule": "Standard legality",
             "detail": "Decks use Standard-legal cards from the implemented pool."},
        ],
    },
]

NOTES = [
    "Game setup (opening hand placement) is auto-resolved with a rules-legal policy so agents focus on in-game decisions.",
    "MCTS uses determinized search over the current state — a documented simplification.",
    "Card effects are implemented per card; the Card Explorer browses the full official list for reference.",
]


def rules_payload() -> dict:
    total = sum(len(g["items"]) for g in RULES)
    return {"groups": RULES, "notes": NOTES, "count": total}
