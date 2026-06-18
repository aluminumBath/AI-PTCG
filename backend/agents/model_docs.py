"""Detailed model/agent documentation.

Powers the "model explainer" modal: for each agent we record *why* it was chosen,
*how* it works, and *what its variables mean* (with the values actually used).
The leaderboard labels/families come from the registry; this adds the prose.
"""
from __future__ import annotations

from .registry import REGISTRY


def _p(name, value, why):
    return {"name": name, "value": str(value), "why": why}


MODEL_DOCS: dict[str, dict] = {
    "random": {
        "why": "The control. Every other agent has to beat random by a wide margin to justify its complexity; it also sanity-checks that the rules engine produces legal games from any line of play.",
        "how": "Picks uniformly at random from the legal actions each turn. No evaluation, no memory.",
        "params": [],
        "strengths": ["Zero cost", "Unbiased baseline"],
        "weaknesses": ["No strategy whatsoever"],
        "imperfect_info": "Trivially safe — it ignores all information.",
    },
    "heuristic": {
        "why": "A strong, fast, fully-explainable opponent that encodes how a person actually plays the deck. It is the rollout policy inside the search agents, so its quality lifts MCTS/ISMCTS too.",
        "how": "Applies hand-authored priorities in order: develop the board (bench Basics, evolve toward the win condition), attach energy to the intended attacker, then attack only when the attack is lethal or nothing better is available (since attacking ends the turn).",
        "params": [],
        "strengths": ["Fast", "Transparent", "No setup or training"],
        "weaknesses": ["Fixed plan — won't discover novel lines", "Can be exploited by an adaptive opponent"],
        "imperfect_info": "Safe — decisions use only the player's own hand and the public board.",
    },
    "greedy": {
        "why": "The simplest principled search and a clean ablation: it isolates 'how good is a one-ply look at the board?' against the rule-based Heuristic and the deeper Minimax.",
        "how": "For every legal move it simulates the move, scores the resulting board with the shared static evaluation, and plays the best — with no model of the opponent's reply.",
        "params": [_p("lookahead", "1 ply", "Evaluates only the state its own move leaves; no opponent response is searched.")],
        "strengths": ["Fast", "Objective-driven"],
        "weaknesses": ["Short-sighted — ignores the opponent's answer", "Can walk into obvious counter-attacks"],
        "imperfect_info": "Safe — the static evaluation reads public board features.",
    },
    "aggro": {
        "why": "A distinct *strategy*, not just another tuning: it tests how a relentless prize-race plan fares — useful on the ladder, where varied strategies make the ratings meaningful.",
        "how": "Scores the board each move would leave behind with weights that prize lowering the opponent's HP and taking prizes, almost ignore its own HP, and add a large bonus for attacking. It will attack even when it isn't lethal if that trades well.",
        "params": [
            _p("attack bias", "+40", "Strong nudge toward ATTACK so it applies pressure every turn."),
            _p("opp-HP weight", "high", "Rewards chipping the opponent down, not just KOs."),
            _p("own-HP weight", "low", "Willing to take damage to deal it — it races."),
        ],
        "strengths": ["Punishes slow openings", "Closes games quickly"],
        "weaknesses": ["Over-extends into removal", "Weak against healing/control"],
        "imperfect_info": "Safe — scores public board features only.",
    },
    "control": {
        "why": "The strategic opposite of aggro, chosen so the roster spans real archetypes: it grinds rather than races, which stresses-tests aggressive opponents and the rating system.",
        "how": "Weights its own board HP, a wide bench and rule-box attackers heavily (so Potion/heal and benching score well) and keeps the attack bias low — it attacks mainly when doing so improves prizes or board.",
        "params": [
            _p("own-HP weight", "high", "Prefers lines that keep its Pokémon healthy."),
            _p("bench weight", "+14", "Values a wide, resilient board."),
            _p("attack bias", "+6", "Low — it won't trade recklessly."),
        ],
        "strengths": ["Out-sustains aggro", "Stable, low-variance"],
        "weaknesses": ["Can be too passive", "May lose the prize race to fast decks"],
        "imperfect_info": "Safe — scores public board features only.",
    },
    "setup": {
        "why": "Represents the build-first / combo plan: it answers whether investing early turns in a board pays off versus immediate aggression, completing the strategic spread.",
        "how": "Weights energy in play, evolutions, a wide bench and rule-box Pokémon highly and biases toward attaching, evolving, benching and abilities — so it assembles a board before committing to attacks (its attack bias is slightly negative early).",
        "params": [
            _p("energy weight", "+16", "Rewards accelerating energy onto the board."),
            _p("evolve / ability bias", "+16 / +12", "Prefers developing its engine first."),
            _p("attack bias", "-6", "Mildly discourages attacking until set up."),
        ],
        "strengths": ["Reaches a strong late-game", "Great with energy acceleration"],
        "weaknesses": ["Can be run over before it sets up", "Slower to take prizes"],
        "imperfect_info": "Safe — scores public board features only.",
    },
    "minimax": {
        "why": "Adds adversarial foresight: chosen to test whether anticipating the opponent's best reply beats acting greedily. It is the cheapest agent that reasons about what the opponent will do.",
        "how": "Searches the move plus the opponent's best response and scores the resulting board with a static evaluation over prizes, board presence, HP, energy and KO threats.",
        "params": [
            _p("opponent_reply", "True", "Searches the opponent's best counter, not just our own move — the difference from Greedy."),
            _p("depth", "1 + reply", "One of our moves and the opponent's answer. Deep enough to avoid one-move blunders while staying fast."),
        ],
        "strengths": ["Avoids one-move blunders", "Still fast"],
        "weaknesses": ["Shallow horizon", "Static eval can misjudge long plans"],
        "imperfect_info": "Approximate — it reasons from the current state and does not model hidden cards.",
    },
    "mcts": {
        "why": "Chosen as the strong perfect-information planner: when it can read the state it plans several moves ahead and beats the Heuristic. It is the reference search agent for the report.",
        "how": "Monte-Carlo Tree Search. Repeatedly selects promising actions by UCB1, expands the tree, plays a heuristic rollout to the end, and backs up win/loss — then plays the most-visited root action.",
        "params": [
            _p("iterations", 120, "Simulations per move. More iterations = stronger but slower; 120 balances strength against turn time."),
            _p("c (exploration)", 1.4, "UCB1 exploration constant (~√2). Higher explores more options; lower exploits the current best."),
            _p("rollout_depth", 40, "Max plies a playout runs before scoring, capping the cost of very long games."),
            _p("rollout_policy", "Heuristic", "Playouts use the Heuristic agent rather than random moves for a much stronger signal."),
        ],
        "strengths": ["Strong lookahead", "Anytime — more time means better play"],
        "weaknesses": ["Slow", "Determinizes over the true state, so it effectively sees hidden cards"],
        "imperfect_info": "Not safe by itself — use ISMCTS for hidden-information play.",
    },
    "flat_mc": {
        "why": "A deliberate contrast to tree search: it shows how much MCTS's selective tree actually buys you versus simply averaging rollouts evenly across moves.",
        "how": "Monte-Carlo evaluation. Gives every legal move the same number of full rollouts, averages the win/draw/loss outcome, and plays the move with the best mean. No tree, no UCB.",
        "params": [
            _p("samples", 12, "Rollouts per legal move. More samples reduce variance at linear cost."),
            _p("rollout_depth", 40, "Max plies per playout before scoring."),
        ],
        "strengths": ["Simple and parallel-friendly", "No tree bookkeeping"],
        "weaknesses": ["Spends budget evenly instead of on promising lines", "Weaker than MCTS at equal cost"],
        "imperfect_info": "Approximate — rollouts run on the current state.",
    },
    "ismcts": {
        "why": "Our answer to the competition's defining property — imperfect information. It was chosen because the contest hides the opponent's hand, both decks' order and the prizes, so an agent must reason over the distribution of hidden states rather than peek.",
        "how": "Information-Set MCTS with root-parallel determinization: each iteration samples a hidden state consistent with everything observable (public board, discards, zone counts), then searches that sample. Visits are aggregated across many samples, so the chosen move is robust to what it cannot see.",
        "params": [
            _p("iterations", 140, "Total simulations per move across all determinizations."),
            _p("determinizations", 8, "Independent hidden-state samples; the move is the consensus across them. More samples = steadier under uncertainty."),
            _p("c (exploration)", 1.4, "UCB1 exploration constant inside each sampled tree."),
            _p("rollout_depth", 40, "Max plies per playout."),
        ],
        "strengths": ["Built for imperfect information", "Doesn't exploit hidden cards"],
        "weaknesses": ["Slow", "Quality depends on the hidden-state sampling assumptions"],
        "imperfect_info": "Safe by design — this is the imperfect-information agent.",
    },
    "rl": {
        "why": "The learned approach: chosen to show a policy trained purely by self-play, with no hand-authored strategy, and because it reads only the observable encoding — making it naturally safe for imperfect information and fast at inference.",
        "how": "A neural policy/value network trained from scratch with PPO self-play. The state is encoded as a fixed-length vector and each candidate action as a feature vector (a pointer formulation); at play time the policy scores the legal actions and the best is taken.",
        "params": [
            _p("algorithm", "PPO self-play", "Proximal Policy Optimization with league self-play; stable and sample-efficient for this size."),
            _p("temperature", 0.0, "0 = greedy (always the top action) for evaluation; raise it to sample for exploration during training."),
            _p("state_dim", 64, "Length of the encoded observation vector fed to the network."),
            _p("value_head", "no Tanh", "The value head is unbounded so it can express decisive winning/losing positions."),
        ],
        "strengths": ["Fast at inference", "Imperfect-information safe (observable encoding only)", "Improves with more training"],
        "weaknesses": ["Only as good as its training budget", "Less interpretable than rules/search"],
        "imperfect_info": "Safe — trained and run on the observable encoding.",
    },
    "rl_mcts": {
        "why": "The hybrid (AlphaZero-style) agent: chosen to combine the learned value network's judgement with the lookahead of search, testing whether guidance at the leaves beats heuristic rollouts.",
        "how": "MCTS where leaf nodes are evaluated by the trained value network instead of (or alongside) a rollout, focusing search on positions the network judges promising.",
        "params": [
            _p("iterations", 120, "Simulations per move."),
            _p("leaf_eval", "value network", "Leaves are scored by the trained net rather than a random/heuristic playout."),
            _p("c (exploration)", 1.4, "UCB1 exploration constant."),
        ],
        "strengths": ["Combines learned judgement with search", "Strong when the value net is well-trained"],
        "weaknesses": ["Slow", "Inherits the value net's blind spots"],
        "imperfect_info": "Approximate — search runs on the current state; the value net itself is observation-based.",
    },
    "council": {
        "why": "An experiment in the wisdom of crowds: if no single model is reliably best, does pooling every model's vote beat any of them individually?",
        "how": "Each non-random model picks its preferred move; the moves are mapped to a canonical key and the one with the highest total (weighted) vote is played. Stronger families carry more weight, and ties break toward the strongest member. Search members run on reduced budgets so the council stays responsive.",
        "params": [
            _p("members", "11", "Every model except random and the meta-agents."),
            _p("weights", "by strength", "Learned/hidden-info models weigh more than baselines."),
            _p("tie-break", "rl_mcts", "Ties resolve toward the strongest member's pick."),
        ],
        "strengths": ["Robust — averages out any one model's blind spot", "No single point of failure"],
        "weaknesses": ["Slow (runs many models per move)", "A bloc of weak voters can outvote a strong one"],
        "imperfect_info": "Safe — members handle information sets individually.",
    },
    "prime": {
        "why": "The deliberate best-of: rather than letting weak models dilute the vote (as in the council), it combines only the strongest traits from each family and adds an adversarial safety check.",
        "how": "A weighted vote of the learned + search + hidden-info + rule-based elite (rl_mcts, ismcts, rl, heuristic). The winning move is then run through a one-ply opponent reply (Minimax-style); if a simpler, safer move scores clearly better against that reply, Prime takes the safer move instead.",
        "params": [
            _p("voters", "rl_mcts · ismcts · rl · heuristic", "One strong representative per family."),
            _p("safety margin", 120, "How much better the safe move must score to override the vote."),
            _p("reply model", "heuristic", "Used to simulate the opponent's answer for the veto."),
        ],
        "strengths": ["High-quality, low-variance decisions", "Won't walk into an obvious punish"],
        "weaknesses": ["Slow", "Conservative — the veto can pass up risky-but-winning lines"],
        "imperfect_info": "Strong — built on ISMCTS determinization plus observation-based models.",
    },
    "meta_top3": {
        "why": "A self-updating champion: instead of fixing which models to trust, it always defers to whatever is currently winning, so it improves automatically as the leaderboard shifts.",
        "how": "Reads the scoreboard ranking, takes the top 3 models, and votes among them (1st place weighted most). It re-resolves the leaderboard on a short timer, so once standings change the line-up follows within seconds. Before any games it falls back to a sensible default trio.",
        "params": [
            _p("source", "scoreboard win-rate", "The Model-scores leaderboard, excluding random and meta-agents."),
            _p("members", "top 3", "Re-selected whenever the standings change."),
            _p("refresh", "5s TTL", "How often it re-checks the leaderboard."),
        ],
        "strengths": ["Adapts as models improve or training progresses", "Always backs the current best"],
        "weaknesses": ["Only as good as the current leaders", "Needs scoreboard data to specialise"],
        "imperfect_info": "Depends on its current members (typically safe).",
    },
}


def model_docs() -> list[dict]:
    out = []
    for mid, meta in REGISTRY.items():
        doc = MODEL_DOCS.get(mid, {})
        out.append({
            "id": mid,
            "label": meta.get("label", mid),
            "family": meta.get("family"),
            "speed": meta.get("speed"),
            "summary": meta.get("description"),
            "why": doc.get("why", ""),
            "how": doc.get("how", ""),
            "params": doc.get("params", []),
            "strengths": doc.get("strengths", []),
            "weaknesses": doc.get("weaknesses", []),
            "imperfect_info": doc.get("imperfect_info", ""),
        })
    return out


def model_doc(model_id: str) -> dict | None:
    for d in model_docs():
        if d["id"] == model_id:
            return d
    return None
