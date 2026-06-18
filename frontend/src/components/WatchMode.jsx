import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { useAuth } from '../auth';
import Board from './Board';
import ImageDisclaimer from './ImageDisclaimer';
import { useFavorites } from '../favorites';

function orderByFav(decks, favDecks) {
  const fav = favDecks || [];
  return [...decks].sort((a, b) => (fav.includes(b) ? 1 : 0) - (fav.includes(a) ? 1 : 0));
}
const deckLabel = (d, favDecks) => ((favDecks || []).includes(d) ? `★ ${d}` : d);

function EventLog({ lines, live }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [lines]);
  return (
    <div className="panel pad">
      <div className="row between" style={{ marginBottom: 10 }}>
        <b style={{ fontFamily: 'var(--display)' }}>Telemetry</b>
        {live && <span className="live"><span className="blip" /> live</span>}
      </div>
      <div className="log" ref={ref}>
        {lines.length === 0 && <div className="ln">Awaiting first move…</div>}
        {lines.map((l, i) => {
          const m = l.match(/^(T\d+:)\s*(.*)$/);
          return <div className="ln" key={i}>{m ? <><span className="t">{m[1]}</span>{m[2]}</> : l}</div>;
        })}
      </div>
    </div>
  );
}

export default function WatchMode({ decks, agents, initialDeck, launchKey }) {
  const { user } = useAuth();
  const { favs } = useFavorites();
  const AGENTS = agents && agents.length ? agents
    : [{ id: 'heuristic', label: 'Heuristic' }, { id: 'mcts', label: 'MCTS' }];
  const [cfg, setCfg] = useState({ deck_a: 'charizard_ex', deck_b: 'gardevoir_ex', agent_a: 'heuristic', agent_b: 'mcts' });
  useEffect(() => { if (initialDeck) setCfg((c) => ({ ...c, deck_a: initialDeck })); }, [initialDeck, launchKey]);
  const [game, setGame] = useState(null);
  const [state, setState] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const timer = useRef(null);

  const done = state?.winner != null || state?.phase === 'game_over';

  async function start() {
    setPlaying(false); setSaved(false);
    const g = await api.newGame({ mode: 'ai_vs_ai', ...cfg });
    setGame(g.game_id); setState(g.state);
  }

  async function stepOnce() {
    if (!game) return;
    const r = await api.step(game);
    setState(r.state);
    return r.done;
  }

  useEffect(() => {
    if (!playing || !game) return;
    let stop = false;
    (async function loop() {
      while (!stop) {
        const d = await stepOnce();
        if (d) { setPlaying(false); break; }
        await new Promise((res) => (timer.current = setTimeout(res, 650)));
      }
    })();
    return () => { stop = true; clearTimeout(timer.current); };
  }, [playing, game]);

  const cur = state?.current_player;

  return (
    <div>
      <ImageDisclaimer />
      <div className="page-head">
        <div className="eyebrow">Mode · Spectate</div>
        <h1>Watch agents duel</h1>
        <p className="sub">Pit any two brains against each other on real Standard decks. The active side glows in its Pokémon's energy type; the prize track fills as KOs land.</p>
      </div>

      <div className="panel pad" style={{ marginBottom: 16 }}>
        <div className="row">
          <label className="field">Deck A
            <select value={cfg.deck_a} onChange={(e) => setCfg({ ...cfg, deck_a: e.target.value })}>
              {orderByFav(decks, favs.decks).map((d) => <option key={d} value={d}>{deckLabel(d, favs.decks)}</option>)}
            </select>
          </label>
          <label className="field">Brain A
            <select value={cfg.agent_a} onChange={(e) => setCfg({ ...cfg, agent_a: e.target.value })}>
              {AGENTS.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
            </select>
          </label>
          <div style={{ fontFamily: 'var(--mono)', color: 'var(--faint)', padding: '0 6px', alignSelf: 'end', paddingBottom: 9 }}>vs</div>
          <label className="field">Deck B
            <select value={cfg.deck_b} onChange={(e) => setCfg({ ...cfg, deck_b: e.target.value })}>
              {orderByFav(decks, favs.decks).map((d) => <option key={d} value={d}>{deckLabel(d, favs.decks)}</option>)}
            </select>
          </label>
          <label className="field">Brain B
            <select value={cfg.agent_b} onChange={(e) => setCfg({ ...cfg, agent_b: e.target.value })}>
              {AGENTS.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
            </select>
          </label>
          <div className="grow" />
          <button className="btn primary" onClick={start} style={{ alignSelf: 'end' }}>New match</button>
        </div>
      </div>

      {state && (
        <>
          <div className="row between" style={{ marginBottom: 14 }}>
            <div className="row">
              <span className="pill">Turn {state.turn_number}</span>
              <span className="tag">{cur === 0 ? state.players[0].name : state.players[1].name} to act</span>
              {state.stadium && <span className="tag">stadium · {state.stadium}</span>}
            </div>
            <div className="row">
              <button className="btn sm" disabled={done} onClick={stepOnce}>Step</button>
              <button className="btn sm primary" disabled={done} onClick={() => setPlaying((p) => !p)}>
                {playing ? 'Pause' : 'Auto-play'}
              </button>
            </div>
          </div>

          {done && (
            <div className="banner row between" style={{ marginBottom: 14 }}>
              <span className="winner">
                {state.winner != null ? `${state.players[state.winner].name} wins` : 'Game over'}
              </span>
              {user && (
                <button className="btn sm" disabled={saved} onClick={async () => { await api.saveGame(game); setSaved(true); }}>
                  {saved ? 'Saved ✓' : 'Save to history'}
                </button>
              )}
            </div>
          )}

          <div className="arena" style={{ marginBottom: 16 }}>
            <Board player={state.players[1]} activeTurn={cur === 1} flip />
            <Board player={state.players[0]} activeTurn={cur === 0} />
          </div>

          <EventLog lines={state.log || []} live={playing} />
        </>
      )}
    </div>
  );
}
