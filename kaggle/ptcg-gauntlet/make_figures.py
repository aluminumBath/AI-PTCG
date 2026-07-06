"""Render the two Strategy-writeup figures from the measured gauntlet results.

Data below is the exact output of gauntlet_eval.py in this session (search vs
heuristic, 8 games/deck; Abomasnow vs field, 8 games/matchup). These are pure
win-rate charts of our own result data — no Pokemon imagery — so they are
license-compliant for the media gallery.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# (deck, search wins / 8) from the SKILL TEST
SKILL = [
    ("bloodmoon_colorless", 8), ("hops_zacian_metal", 7), ("genesect_metal", 6),
    ("keldeo_water", 6), ("mewtwo_rocket", 6), ("pikachu_lightning", 6),
    ("regirock_fighting", 6), ("terapagos_colorless", 6), ("volcanion_fire", 6),
    ("black_kyurem_water", 5), ("gouging_fire", 5), ("iron_leaves_grass", 5),
    ("koraidon_fighting", 5), ("latias_psychic", 4), ("yveltal_dark", 4),
]
# (deck, Abomasnow wins, losses) from the DECK TEST
DECK = [
    ("black_kyurem_water", 8, 0), ("bloodmoon_colorless", 8, 0), ("gouging_fire", 8, 0),
    ("koraidon_fighting", 8, 0), ("pikachu_lightning", 8, 0), ("volcanion_fire", 8, 0),
    ("iron_leaves_grass", 7, 1), ("keldeo_water", 7, 1), ("mewtwo_rocket", 7, 1),
    ("regirock_fighting", 7, 1), ("yveltal_dark", 7, 1), ("latias_psychic", 6, 2),
    ("terapagos_colorless", 6, 2), ("genesect_metal", 4, 4), ("hops_zacian_metal", 4, 4),
]

BLUE, GREY, RED = "#2b6cb0", "#a0aec0", "#c53030"


def fig1():
    labels = [d for d, _ in SKILL]
    rates = [w / 8 * 100 for _, w in SKILL]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    y = range(len(labels))
    ax.barh(list(y), rates, color=[BLUE if r >= 50 else RED for r in rates])
    ax.axvline(50, color="black", lw=1, ls="--", alpha=0.7)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Search-agent win-rate vs. heuristic (%)")
    ax.set_xlim(0, 100)
    ax.set_title("Figure 1 — Agent skill across 15 decks (70.8% overall, \u226550% every deck)")
    for i, r in enumerate(rates):
        ax.text(r + 1.5, i, f"{r:.0f}%", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig("/mnt/user-data/outputs/figures/fig1_agent_skill.png", dpi=150)
    plt.close(fig)


def fig2():
    labels = [d for d, _, _ in DECK]
    rates = [w / (w + l) * 100 for _, w, l in DECK]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    y = range(len(labels))
    colors = [BLUE if r > 50 else GREY for r in rates]
    ax.barh(list(y), rates, color=colors)
    ax.axvline(50, color="black", lw=1, ls="--", alpha=0.7)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Mega Abomasnow ex win-rate vs. opponent deck (%)")
    ax.set_xlim(0, 100)
    ax.set_title("Figure 2 — Deck matchup spread (85.8% overall; Metal = soft spot)")
    for i, r in enumerate(rates):
        ax.text(r + 1.5, i, f"{r:.0f}%", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig("/mnt/user-data/outputs/figures/fig2_deck_spread.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    import os
    os.makedirs("/mnt/user-data/outputs/figures", exist_ok=True)
    fig1()
    fig2()
    print("wrote fig1_agent_skill.png and fig2_deck_spread.png")
