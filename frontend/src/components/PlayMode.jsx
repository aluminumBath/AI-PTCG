import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import Board from './Board';

const AGENTS = [
  { id: 'heuristic', label: 'Heuristic' },
  { id: 'mcts', label: 'MCTS (search)' },
  { id: 'rl', label: 'RL policy' },
  { id: 'random', label: 'Random' },
];

export default function PlayMode({ decks }) {
  const [cfg, setCfg] = useState({ deck_a: 'charizard_ex', deck_b: 'gardevoir_ex', agent_b: 'mcts' });
  const [game, setGame] = useState(null);
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const logRef = useRef(null);

  const done = state?.winner != null || state?.phase === 'game_over';
  const myTurn = state && state.current_player === 0 && !done;
  const legal = state?.legal_actions || [];

  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [state]);

  async function start() {
    const g = await api.newGame({ mode: 'human_vs_ai', human_seat: 0, deck_a: cfg.deck_a, deck_b: cfg.deck_b, agent_b: cfg.agent_b });
    setGame(g.game_id); setState(g.state);
  }

  async function play(index) {
    if (busy) return;
    setBusy(true);
    try { const r = await api.action(game, index); setState(r.state); }
    finally { setBusy(false); }
  }

  function trayClass(t) {
    if (t === 'attack') return 'act-btn attack';
    if (t === 'end_turn') return 'act-btn end';
    return 'act-btn';
  }

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Mode · Play</div>
        <h1>Play against the AI</h1>
        <p className="sub">You pilot Deck A. Pick an action each turn from the tray; the AI takes its full turn in response. Attacks end your turn, so develop your board first.</p>
      </div>

      <div className="panel pad" style={{ marginBottom: 16 }}>
        <div className="row">
          <label className="field">Your deck
            <select value={cfg.deck_a} onChange={(e) => setCfg({ ...cfg, deck_a: e.target.value })}>
              {decks.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <label className="field">Opponent deck
            <select value={cfg.deck_b} onChange={(e) => setCfg({ ...cfg, deck_b: e.target.value })}>
              {decks.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <label className="field">Opponent brain
            <select value={cfg.agent_b} onChange={(e) => setCfg({ ...cfg, agent_b: e.target.value })}>
              {AGENTS.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
            </select>
          </label>
          <div className="grow" />
          <button className="btn primary" onClick={start} style={{ alignSelf: 'end' }}>New game</button>
        </div>
      </div>

      {state && (
        <>
          <div className="row between" style={{ marginBottom: 14 }}>
            <div className="row">
              <span className="pill">Turn {state.turn_number}</span>
              <span className="tag">{myTurn ? 'your move' : (busy ? 'AI thinking…' : 'opponent turn')}</span>
            </div>
          </div>

          {done && (
            <div className="banner" style={{ marginBottom: 14 }}>
              <span className="winner">{state.winner === 0 ? 'You win! 🏆' : 'You lost'}</span>
            </div>
          )}

          <div className="arena" style={{ marginBottom: 16 }}>
            <Board player={state.players[1]} activeTurn={state.current_player === 1} flip />
            <Board player={state.players[0]} activeTurn={myTurn} />
          </div>

          <div className="panel pad" style={{ marginBottom: 16 }}>
            <div className="row between" style={{ marginBottom: 10 }}>
              <b style={{ fontFamily: 'var(--display)' }}>Your actions</b>
              {busy && <span className="live"><span className="spin" /> resolving</span>}
            </div>
            {myTurn ? (
              <div className="tray">
                {legal.map((a) => (
                  <button key={a.index} className={trayClass(a.type)} disabled={busy} onClick={() => play(a.index)}>
                    {a.label}
                  </button>
                ))}
              </div>
            ) : (
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>
                {done ? 'Game over — start a new game above.' : 'Waiting for the opponent…'}
              </div>
            )}
          </div>

          <div className="panel pad">
            <b style={{ fontFamily: 'var(--display)' }}>Telemetry</b>
            <div className="log" ref={logRef} style={{ marginTop: 10 }}>
              {(state.log || []).map((l, i) => {
                const m = l.match(/^(T\d+:)\s*(.*)$/);
                return <div className="ln" key={i}>{m ? <><span className="t">{m[1]}</span>{m[2]}</> : l}</div>;
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
