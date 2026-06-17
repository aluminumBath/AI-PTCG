"""The rules engine.

``GameEngine`` owns a ``GameState`` and exposes the two methods agents care
about: ``legal_actions()`` and ``apply(action)``. Everything else — the draw
step, status checks between turns, weakness/resistance, KO and prize handling,
win-condition checks — is driven internally so that any agent (random,
heuristic, MCTS, or the RL policy) plays by identical, faithful rules.
"""
from __future__ import annotations

import copy
import random
from typing import Optional

from .actions import Action, ActionType
from .cards import CardDef, CardInstance
from .effects import EffectContext, get_effect
from .enums import (
    BENCH_SIZE,
    EnergyType,
    Phase,
    PRIZE_COUNT,
    STARTING_HAND,
    Stage,
    StatusCondition,
    TrainerKind,
)
from .state import GameState, PlayerState


class GameEngine:
    def __init__(self, state: GameState, rng: Optional[random.Random] = None):
        self.state = state
        self.rng = rng or random.Random(state.rng_seed)

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    @classmethod
    def new_game(
        cls,
        deck_a: list[CardDef],
        deck_b: list[CardDef],
        names: tuple[str, str] = ("Agent A", "Agent B"),
        seed: int = 0,
    ) -> "GameEngine":
        rng = random.Random(seed)
        players = [PlayerState(index=0, name=names[0]), PlayerState(index=1, name=names[1])]
        for pi, deck in enumerate((deck_a, deck_b)):
            players[pi].deck = [CardInstance(card=c, owner=pi) for c in deck]
        state = GameState(players=players, rng_seed=seed)
        eng = cls(state, rng)
        eng._setup()
        return eng

    def log(self, msg: str) -> None:
        self.state.log_event(msg)

    # ------------------------------------------------------------------ #
    # Setup (mulligan-aware, auto-resolved opening board)
    # ------------------------------------------------------------------ #
    def _setup(self) -> None:
        s = self.state
        for p in s.players:
            self._draw_opening_hand(p)

        s.first_player = self.rng.randint(0, 1)
        s.current_player = s.first_player

        # Place a Basic as Active + bench remaining basics (guided auto-setup).
        for p in s.players:
            basics = [c for c in p.hand if c.card.is_basic_pokemon]
            basics.sort(key=lambda c: c.card.hp, reverse=True)
            active = basics[0]
            p.hand.remove(active)
            active.turn_played = 0
            active.summoning_sick = False
            p.active = active
            for b in basics[1:1 + BENCH_SIZE]:
                p.hand.remove(b)
                b.turn_played = 0
                b.summoning_sick = False
                p.bench.append(b)

        # Prizes
        for p in s.players:
            for _ in range(PRIZE_COUNT):
                if p.deck:
                    p.prizes.append(p.deck.pop(0))

        s.phase = Phase.DRAW
        s.turn_number = 1
        self.log(f"{s.players[s.first_player].name} goes first.")
        self._begin_turn(first_turn=True)

    def _draw_opening_hand(self, p: PlayerState) -> None:
        mulligans = 0
        while True:
            p.shuffle_deck(self.rng)
            p.hand = []
            p.draw(STARTING_HAND)
            if any(c.card.is_basic_pokemon for c in p.hand):
                break
            # mulligan: shuffle back and redraw
            p.deck.extend(p.hand)
            p.hand = []
            mulligans += 1
            if mulligans > 15:
                break  # pathological deck guard

    # ------------------------------------------------------------------ #
    # Turn lifecycle
    # ------------------------------------------------------------------ #
    def _begin_turn(self, first_turn: bool = False) -> None:
        s = self.state
        p = s.current
        p.reset_turn_flags()
        for poke in p.all_pokemon():
            poke.summoning_sick = False
            poke.can_evolve_this_turn = poke.turn_played < s.turn_number

        # Draw step (the very first player's first turn still draws in current rules).
        drawn = p.draw(1)
        if not drawn and not p.deck:
            # Could not draw -> this player loses (deck-out).
            self._win(s.opponent_of(p.index), reason="deck-out")
            return
        s.phase = Phase.MAIN

    def _end_turn(self) -> None:
        s = self.state
        self._between_turns(s.current)
        if s.is_over():
            return
        s.current_player = s.opponent_of(s.current_player)
        s.turn_number += 1
        self._begin_turn()

    def _between_turns(self, ended_player: PlayerState) -> None:
        """Pokémon Checkup (between turns).

        Per the official rules this resolves Special Conditions on *both*
        players' Active Pokémon: Poisoned (10), Burned (20 + coin flip to remove),
        and Asleep (coin flip to wake). Paralysis is removed during the Checkup
        that follows the affected player's own turn — i.e. for the player whose
        turn just ended. Special Conditions only ever sit on the Active Pokémon.
        """
        s = self.state
        for pl in s.players:
            poke = pl.active
            if not poke:
                continue
            if StatusCondition.POISONED in poke.status:
                self.deal_raw_damage(poke, 10, pl, source_status=True)
            if StatusCondition.BURNED in poke.status:
                self.deal_raw_damage(poke, 20, pl, source_status=True)
                if self.rng.random() < 0.5:
                    poke.status.discard(StatusCondition.BURNED)
            if StatusCondition.ASLEEP in poke.status:
                if self.rng.random() < 0.5:
                    poke.status.discard(StatusCondition.ASLEEP)
        # Paralysis wears off after the controller's own turn.
        if ended_player.active:
            ended_player.active.status.discard(StatusCondition.PARALYZED)
        self._cleanup_knockouts()

    # ------------------------------------------------------------------ #
    # Legal action generation
    # ------------------------------------------------------------------ #
    def legal_actions(self) -> list[Action]:
        s = self.state
        if s.is_over():
            return []
        p = s.current
        actions: list[Action] = [Action(ActionType.END_TURN)]

        if p.active is None:
            # must promote something first
            return self._promote_actions(p)

        active_paralyzed = (
            p.active and StatusCondition.PARALYZED in p.active.status
        )
        active_asleep = p.active and StatusCondition.ASLEEP in p.active.status

        # The player who goes first may neither attack nor evolve on turn 1.
        first_turn_first_player = (
            s.turn_number == 1 and p.index == s.first_player
        )

        for i, card in enumerate(p.hand):
            cd = card.card
            # Play Basic to bench
            if cd.is_basic_pokemon and p.bench_has_space():
                actions.append(Action(ActionType.PLAY_BASIC, hand_index=i))
            # Evolve (not on the first player's first turn, not the turn a
            # Pokémon was played, and not the turn it already evolved).
            if cd.is_pokemon and cd.evolves_from and not first_turn_first_player:
                for tgt in p.all_pokemon():
                    if (
                        tgt.card.name == cd.evolves_from
                        and tgt.can_evolve_this_turn
                        and not tgt.summoning_sick
                    ):
                        actions.append(
                            Action(ActionType.EVOLVE, hand_index=i, target_uid=tgt.uid)
                        )
            # Attach energy (once per turn)
            if cd.is_energy and not p.energy_attached_this_turn:
                for tgt in p.all_pokemon():
                    actions.append(
                        Action(ActionType.ATTACH_ENERGY, hand_index=i, target_uid=tgt.uid)
                    )
            # Trainers
            if cd.is_trainer:
                actions.extend(self._trainer_actions(p, i, cd))

        # Abilities
        for poke in p.all_pokemon():
            for ai, ab in enumerate(poke.card.abilities):
                if ab.kind == "activated" and poke.uid not in p.abilities_used:
                    actions.append(
                        Action(ActionType.USE_ABILITY, source_uid=poke.uid, sub_index=ai)
                    )

        # Retreat (once per turn, not if paralyzed/asleep, needs energy + bench)
        if (
            not p.retreated_this_turn
            and p.bench
            and p.active
            and not active_paralyzed
            and not active_asleep
            and p.active.energy_count() >= p.active.card.retreat_cost
        ):
            for b in p.bench:
                actions.append(
                    Action(ActionType.RETREAT, source_uid=p.active.uid, target_uid=b.uid)
                )

        # Attacks (ends turn). First player cannot attack on turn 1.
        if (
            p.active
            and not active_paralyzed
            and not active_asleep
            and not first_turn_first_player
        ):
            for idx, atk in enumerate(p.active.card.attacks):
                if self._can_pay_attack_cost(p.active, atk.cost):
                    actions.append(
                        Action(ActionType.ATTACK, source_uid=p.active.uid, sub_index=idx)
                    )

        return actions

    def _promote_actions(self, p: PlayerState) -> list[Action]:
        return [
            Action(ActionType.CHOOSE_ACTIVE, target_uid=b.uid) for b in p.bench
        ] or [Action(ActionType.END_TURN)]

    def _trainer_actions(self, p: PlayerState, i: int, cd: CardDef) -> list[Action]:
        out: list[Action] = []
        if cd.trainer_kind == TrainerKind.SUPPORTER:
            if not p.supporter_played_this_turn:
                out.append(Action(ActionType.PLAY_SUPPORTER, hand_index=i))
        elif cd.trainer_kind == TrainerKind.ITEM:
            out.append(Action(ActionType.PLAY_ITEM, hand_index=i))
        elif cd.trainer_kind == TrainerKind.STADIUM:
            if not p.stadium_played_this_turn:
                out.append(Action(ActionType.PLAY_STADIUM, hand_index=i))
        elif cd.trainer_kind == TrainerKind.TOOL:
            for tgt in p.all_pokemon():
                if len(tgt.attached_tools) == 0:
                    out.append(
                        Action(ActionType.ATTACH_TOOL, hand_index=i, target_uid=tgt.uid)
                    )
        return out

    def _can_pay_attack_cost(self, poke: CardInstance, cost: tuple[EnergyType, ...]) -> bool:
        if not cost:
            return True
        provided = poke.provided_energy()
        pool = list(provided)
        # pay typed costs first
        for need in cost:
            if need == EnergyType.COLORLESS:
                continue
            if need in pool:
                pool.remove(need)
            elif EnergyType.COLORLESS in pool:
                # a Colorless-providing energy can't satisfy a typed cost; skip
                return False
            else:
                return False
        colorless_needed = sum(1 for c in cost if c == EnergyType.COLORLESS)
        return len(pool) >= colorless_needed

    # ------------------------------------------------------------------ #
    # Applying actions
    # ------------------------------------------------------------------ #
    def apply(self, action: Action) -> None:
        s = self.state
        if s.is_over():
            return
        p = s.current
        handler = {
            ActionType.PLAY_BASIC: self._do_play_basic,
            ActionType.EVOLVE: self._do_evolve,
            ActionType.ATTACH_ENERGY: self._do_attach_energy,
            ActionType.PLAY_ITEM: self._do_play_trainer,
            ActionType.PLAY_SUPPORTER: self._do_play_trainer,
            ActionType.PLAY_STADIUM: self._do_play_stadium,
            ActionType.ATTACH_TOOL: self._do_attach_tool,
            ActionType.USE_ABILITY: self._do_use_ability,
            ActionType.RETREAT: self._do_retreat,
            ActionType.ATTACK: self._do_attack,
            ActionType.CHOOSE_ACTIVE: self._do_choose_active,
            ActionType.END_TURN: self._do_end_turn,
        }.get(action.type)
        if handler is None:
            raise ValueError(f"Unhandled action {action.type}")
        handler(p, action)

    def _find(self, p: PlayerState, uid: int) -> Optional[CardInstance]:
        for poke in p.all_pokemon():
            if poke.uid == uid:
                return poke
        return None

    def _do_play_basic(self, p: PlayerState, a: Action) -> None:
        card = p.hand.pop(a.hand_index)
        card.turn_played = self.state.turn_number
        card.summoning_sick = True
        card.can_evolve_this_turn = False
        p.bench.append(card)
        self.log(f"{p.name} benched {card.card.name}.")

    def _do_evolve(self, p: PlayerState, a: Action) -> None:
        evo = p.hand.pop(a.hand_index)
        target = self._find(p, a.target_uid)
        if not target:
            p.hand.insert(a.hand_index, evo)
            return
        evo.uid = target.uid  # keep identity/position
        evo.damage = target.damage
        evo.attached_energy = target.attached_energy
        evo.attached_tools = target.attached_tools
        evo.status = set()  # evolving removes Special Conditions
        evo.evolved_from = target.evolved_from + [target.card]
        evo.turn_played = self.state.turn_number
        evo.summoning_sick = False
        evo.can_evolve_this_turn = False
        if p.active and p.active.uid == target.uid:
            p.active = evo
        else:
            p.bench = [evo if b.uid == target.uid else b for b in p.bench]
        self.log(f"{p.name} evolved {target.card.name} -> {evo.card.name}.")

    def _do_attach_energy(self, p: PlayerState, a: Action) -> None:
        energy = p.hand.pop(a.hand_index)
        target = self._find(p, a.target_uid)
        if not target:
            p.hand.insert(a.hand_index, energy)
            return
        target.attached_energy.append(energy)
        p.energy_attached_this_turn = True
        self.log(f"{p.name} attached {energy.card.name} to {target.card.name}.")

    def _do_play_trainer(self, p: PlayerState, a: Action) -> None:
        card = p.hand.pop(a.hand_index)
        if card.card.trainer_kind == TrainerKind.SUPPORTER:
            p.supporter_played_this_turn = True
        target = self._find(self.state.opponent, a.target_uid) or self._find(p, a.target_uid)
        self._resolve_effect(card.card.trainer_effect_id, p, source=None, target=target)
        p.discard.append(card)
        self._cleanup_knockouts()

    def _do_play_stadium(self, p: PlayerState, a: Action) -> None:
        card = p.hand.pop(a.hand_index)
        s = self.state
        if s.stadium:
            owner = s.players[s.stadium_owner]
            owner.discard.append(s.stadium)
        s.stadium = card
        s.stadium_owner = p.index
        p.stadium_played_this_turn = True
        self.log(f"{p.name} played Stadium {card.card.name}.")

    def _do_attach_tool(self, p: PlayerState, a: Action) -> None:
        card = p.hand.pop(a.hand_index)
        target = self._find(p, a.target_uid)
        if target:
            target.attached_tools.append(card)
            self.log(f"{p.name} attached tool {card.card.name} to {target.card.name}.")
        else:
            p.hand.insert(a.hand_index, card)

    def _do_use_ability(self, p: PlayerState, a: Action) -> None:
        source = self._find(p, a.source_uid)
        if not source:
            return
        ab = source.card.abilities[a.sub_index]
        p.abilities_used.add(source.uid)
        self._resolve_effect(ab.effect_id, p, source=source, target=None)
        self._cleanup_knockouts()

    def _do_retreat(self, p: PlayerState, a: Action) -> None:
        target = self._find(p, a.target_uid)
        if not target or not p.active:
            return
        cost = p.active.card.retreat_cost
        self.discard_energy_from(p.active, cost)
        p.active.status = set()  # retreating clears Special Conditions
        self.swap_active(p, target)
        p.retreated_this_turn = True
        self.log(f"{p.name} retreated to {target.card.name}.")

    def _do_choose_active(self, p: PlayerState, a: Action) -> None:
        target = self._find(p, a.target_uid)
        if target and target in p.bench:
            p.bench.remove(target)
            p.active = target
            self.log(f"{p.name} promoted {target.card.name} to Active.")

    def _do_end_turn(self, p: PlayerState, a: Action) -> None:
        self._end_turn()

    # ------------------------------------------------------------------ #
    # Attacking + damage pipeline
    # ------------------------------------------------------------------ #
    def _do_attack(self, p: PlayerState, a: Action) -> None:
        s = self.state
        attacker = self._find(p, a.source_uid)
        if not attacker or not attacker.card.attacks:
            self._end_turn()
            return
        atk = attacker.card.attacks[a.sub_index]
        defender = s.opponent.active

        # Confusion: 50% the attack fails and you self-damage.
        if StatusCondition.CONFUSED in attacker.status and self.rng.random() < 0.5:
            self.deal_raw_damage(attacker, 30, p, source_status=True)
            self.log(f"{attacker.card.name} is Confused and hurt itself!")
            self._cleanup_knockouts()
            self._end_turn()
            return

        if defender and atk.damage > 0:
            dmg = self._compute_damage(attacker, defender, atk)
            self.deal_raw_damage(defender, dmg, s.opponent)
            self.log(
                f"{attacker.card.name} used {atk.name} for {dmg} on {defender.card.name}."
            )

        # Attack side effect
        if atk.effect_id:
            self._resolve_effect(
                atk.effect_id, p, source=attacker, target=defender, base_damage=atk.damage
            )

        self._cleanup_knockouts()
        if not s.is_over():
            self._end_turn()

    def _compute_damage(self, attacker: CardInstance, defender: CardInstance, atk) -> int:
        dmg = atk.damage
        # energy-scaling attacks
        if atk.effect_id == "damage_scales_with_energy_30":
            base_cost = atk.cost_size
            extra = max(0, attacker.energy_count() - base_cost)
            dmg += 30 * extra
        # Weakness (modern rule: ×2)
        if defender.card.weakness and attacker.card.types:
            if defender.card.weakness in attacker.card.types:
                dmg *= defender.card.weakness_mult
        # Resistance
        if defender.card.resistance and attacker.card.types:
            if defender.card.resistance in attacker.card.types:
                dmg = max(0, dmg - defender.card.resistance_amt)
        return dmg

    # ------------------------------------------------------------------ #
    # Shared helpers used by effects
    # ------------------------------------------------------------------ #
    def deal_raw_damage(
        self, poke: CardInstance, amount: int, owner: PlayerState, source_status: bool = False
    ) -> None:
        if amount <= 0:
            return
        poke.damage += amount

    def heal(self, poke: CardInstance, amount: int) -> None:
        poke.damage = max(0, poke.damage - amount)
        self.log(f"{poke.card.name} healed {amount}.")

    def discard_energy_from(self, poke: CardInstance, n: int) -> None:
        for _ in range(n):
            if poke.attached_energy:
                e = poke.attached_energy.pop()
                self.state.players[poke.owner].discard.append(e)

    def swap_active(self, p: PlayerState, new_active: CardInstance) -> None:
        if new_active in p.bench:
            p.bench.remove(new_active)
        old = p.active
        p.active = new_active
        if old:
            old.status = set()  # Special Conditions are removed when benched
            p.bench.append(old)

    def _resolve_effect(self, key, player, source=None, target=None, base_damage=0):
        if not key:
            return
        fn = get_effect(key)
        if fn is None:
            return  # unimplemented effect: no-op (logged in strict mode)
        ctx = EffectContext(
            engine=self,
            player=player,
            opponent=self.state.players[self.state.opponent_of(player.index)],
            source=source,
            target=target,
            base_damage=base_damage,
        )
        fn(ctx)

    # ------------------------------------------------------------------ #
    # Knockouts, prizes, win conditions
    # ------------------------------------------------------------------ #
    def _cleanup_knockouts(self) -> None:
        s = self.state
        for pi, p in enumerate(s.players):
            opp = s.players[s.opponent_of(pi)]
            # check this player's Pokémon for KO; opponent takes prizes
            kos = [poke for poke in p.all_pokemon() if poke.is_knocked_out]
            for poke in kos:
                prizes = poke.prizes_on_ko
                self._knock_out(p, poke)
                self._take_prizes(opp, prizes)
            if kos:
                self.log(f"{len(kos)} of {p.name}'s Pokémon were Knocked Out.")
        self._check_win_conditions()

    def _knock_out(self, p: PlayerState, poke: CardInstance) -> None:
        # discard the Pokémon, its evolution chain, energy and tools
        for e in poke.attached_energy:
            p.discard.append(e)
        for t in poke.attached_tools:
            p.discard.append(t)
        for base in poke.evolved_from:
            p.discard.append(CardInstance(card=base, owner=p.index))
        p.discard.append(poke)
        if p.active and p.active.uid == poke.uid:
            p.active = None
        else:
            p.bench = [b for b in p.bench if b.uid != poke.uid]

    def _take_prizes(self, p: PlayerState, n: int) -> None:
        for _ in range(n):
            if p.prizes:
                p.hand.append(p.prizes.pop())
                p.prizes_taken += 1

    def _check_win_conditions(self) -> None:
        s = self.state
        if s.is_over():
            return
        for pi, p in enumerate(s.players):
            opp = s.players[s.opponent_of(pi)]
            if len(p.prizes) == 0:
                self._win(pi, reason="all prizes taken")
                return
            if not opp.has_pokemon_in_play() and s.turn_number > 1:
                self._win(pi, reason="opponent has no Pokémon")
                return

    def _win(self, player_idx: int, reason: str) -> None:
        s = self.state
        s.winner = player_idx
        s.phase = Phase.GAME_OVER
        self.log(f"{s.players[player_idx].name} wins ({reason}).")

    # ------------------------------------------------------------------ #
    # Cloning (for MCTS / search)
    # ------------------------------------------------------------------ #
    def clone(self) -> "GameEngine":
        new_state = copy.deepcopy(self.state)
        return GameEngine(new_state, random.Random(self.rng.random()))
