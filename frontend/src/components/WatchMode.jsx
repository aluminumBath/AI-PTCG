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

function HandChips({ cards }) {
  return (
    <div style={{ marginTop: 8 }}>
      <div className="sub" style={{ fontSize: 11, marginBottom: 4 }}>Likely in hand (neural model):</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {cards.map((c) => (
          <span key={c.name} className="tag" style={{ fontSize: 11 }}>{c.name} · {Math.round((c.prob || 0) * 100)}%</span>
        ))}
      </div>
    </div>
  );
}

function ReadBars({ read, title }) {
  if (!read || !read.revealed) return null;
  return (
    <div className="panel pad" style={{ marginBottom: 14, fontSize: 13, flex: 1 }}>
      <div className="row between">
        <b style={{ fontFamily: 'var(--display)' }}>{title}</b>
        <span className="sub">{read.style} · {Math.round((read.confidence || 0) * 100)}% top</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
        {read.top.map((t) => {
          const pct = Math.round((t.prob || 0) * 100);
          return (
            <div key={t.deck_id} className="row" style={{ gap: 8, alignItems: 'center' }}>
              <span style={{ width: 118, fontSize: 12 }}>{t.deck_id.replace(/_/g, ' ')}</span>
              <div style={{ flex: 1, background: 'var(--panel-2, #1c1c22)', borderRadius: 5, height: 12, overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: 'var(--psychic, #b07bd4)' }} />
              </div>
              <span style={{ width: 38, textAlign: 'right', fontSize: 11, color: 'var(--muted)' }}>{pct}%</span>
            </div>
          );
        })}
      </div>
      {read.hand_read && read.hand_read.length > 0 && <HandChips cards={read.hand_read} />}
      <p className="sub" style={{ marginTop: 6, fontSize: 11 }}>Inferred from the public cards the opponent has revealed.</p>
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
  const [move, setMove] = useState(null);
  const [readView, setReadView] = useState('mover');
  const [readAcc, setReadAcc] = useState({ sum: 0, n: 0, last: null });
  const timer = useRef(null);

  const done = state?.winner != null || state?.phase === 'game_over';

  async function start() {
    setPlaying(false); setSaved(false); setMove(null);
    setReadAcc({ sum: 0, n: 0, last: null });
    const g = await api.newGame({ mode: 'ai_vs_ai', ...cfg });
    setGame(g.game_id); setState(g.state);
  }

  async function stepOnce() {
    if (!game) return;
    const r = await api.step(game);
    setState(r.state);
    setMove({ action: r.last_action, rationale: r.rationale, read: r.opponent_read, reads: r.reads });
    const ev = r.opponent_read?.read_eval;
    if (ev) setReadAcc((s) => ({ sum: s.sum + ev.precision_at_hand, n: s.n + 1, last: ev }));
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
        <p className="sub">Pit any two brains against each other on real Standard decks — or set a deck to <b>🎲 Random</b> or <b>🤖 Agent's pick</b> (a deck matching that agent's style). The chosen deck shows on each side once the match starts. The active side glows in its Pokémon's energy type; the prize track fills as KOs land.</p>
      </div>

      <div className="panel pad" style={{ marginBottom: 16 }}>
        <div className="row">
          <label className="field">Deck A
            <select value={cfg.deck_a} onChange={(e) => setCfg({ ...cfg, deck_a: e.target.value })}>
              <option value="auto">🤖 Agent's pick</option>
              <option value="random">🎲 Random deck</option>
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
              <option value="auto">🤖 Agent's pick</option>
              <option value="random">🎲 Random deck</option>
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

          {move && (move.rationale || move.action) && (
            <div className="panel pad" style={{ marginBottom: 14, fontSize: 13 }}>
              {move.rationale
                ? <span><b>Why:</b> {move.rationale}</span>
                : <span className="sub mono">{move.action}</span>}
            </div>
          )}

          {move && (move.read?.revealed > 0 || move.reads?.['0']?.revealed > 0 || move.reads?.['1']?.revealed > 0) && (
            <div style={{ marginBottom: 14 }}>
              <div className="row between" style={{ marginBottom: 6 }}>
                <span className="sub" style={{ fontSize: 12 }}>Opponent read</span>
                <div className="row" style={{ gap: 6 }}>
                  <button className="btn sm" style={{ opacity: readView === 'mover' ? 1 : 0.5 }} onClick={() => setReadView('mover')}>mover</button>
                  <button className="btn sm" style={{ opacity: readView === 'both' ? 1 : 0.5 }} onClick={() => setReadView('both')}>both</button>
                </div>
              </div>
              {readView === 'mover'
                ? <ReadBars read={move.read} title={`Read of opponent${move.read?.agent ? ' · ' + move.read.agent : ''}`} />
                : (
                  <div className="row" style={{ gap: 12, alignItems: 'stretch' }}>
                    <ReadBars read={move.reads?.['0']} title={`${cfg.agent_a} → opp`} />
                    <ReadBars read={move.reads?.['1']} title={`${cfg.agent_b} → opp`} />
                  </div>
                )}
              {readView === 'mover' && readAcc.last && (
                <div className="sub" style={{ fontSize: 11, marginTop: -4 }}>
                  Read accuracy — this move {readAcc.last.hits}/{readAcc.last.hand_size} hand cards in top guesses;
                  avg precision {Math.round((100 * readAcc.sum) / readAcc.n)}% over {readAcc.n} moves ·
                  P(in-hand) {readAcc.last.p_in} vs P(other) {readAcc.last.p_out}
                </div>
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
