import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import Board from './Board';
import ImageDisclaimer from './ImageDisclaimer';
import { useFavorites } from '../favorites';

const MP_KEY = 'tcg.mp.match';

function orderByFav(decks, favDecks) {
  const fav = favDecks || [];
  return [...(decks || [])].sort((a, b) => (fav.includes(b) ? 1 : 0) - (fav.includes(a) ? 1 : 0));
}
const deckLabel = (d, favDecks) => ((favDecks || []).includes(d) ? `★ ${d}` : d);

function LearnedPanel() {
  const [data, setData] = useState(null);
  const [job, setJob] = useState(null);
  const poll = useRef(null);

  const load = () => api.mpLearned().then(setData).catch(() => {});
  useEffect(() => { load(); return () => clearInterval(poll.current); }, []);

  async function teach() {
    const { job_id } = await api.mpLearn(6);
    setJob({ status: 'running', history: [] });
    clearInterval(poll.current);
    poll.current = setInterval(async () => {
      const s = await api.mpLearnStatus(job_id);
      setJob(s);
      if (s.status !== 'running') { clearInterval(poll.current); load(); }
    }, 1200);
  }

  if (!data) return null;
  const mix = Object.entries(data.winner_action_mix || {});
  const maxMix = Math.max(1, ...mix.map(([, n]) => n));

  return (
    <div className="panel pad" style={{ marginTop: 16 }}>
      <div className="row between">
        <b style={{ fontFamily: 'var(--display)' }}>Learn from the winners</b>
        <div className="row" style={{ gap: 8 }}>
          <a className="btn sm" href={api.mpDatasetUrl()} target="_blank" rel="noreferrer">Export dataset</a>
          <button className="btn primary sm" onClick={teach} disabled={!data.can_learn || job?.status === 'running'}>
            {job?.status === 'running' ? <span className="spin" /> : 'Teach the agents'}
          </button>
        </div>
      </div>
      <p className="sub" style={{ fontSize: 12.5, marginTop: 8 }}>
        Every finished match stores the <b>winner's</b> moves as training examples. “Teach the agents” behaviourally-clones
        those moves into the RL policy used by the <span className="mono">rl</span> and <span className="mono">rl_mcts</span> agents,
        so they pick up strategies that won here. {data.can_learn ? '' : 'Play at least one match to a finish first.'}
      </p>

      <div className="row" style={{ gap: 18, flexWrap: 'wrap', marginTop: 6 }}>
        <span className="tag">{data.total_games} games captured</span>
        <span className="tag">{data.total_samples} winning moves</span>
      </div>

      {mix.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className="kc-label">What winners did most</div>
          {mix.slice(0, 8).map(([k, n]) => (
            <div key={k} className="mixrow">
              <span className="mixlabel">{k.replace(/_/g, ' ')}</span>
              <span className="mixbar"><i style={{ width: `${(100 * n) / maxMix}%` }} /></span>
              <span className="mixn">{n}</span>
            </div>
          ))}
        </div>
      )}

      {job && (
        <div className="sub" style={{ fontSize: 12, marginTop: 10 }}>
          {job.status === 'running' ? 'Cloning winning strategies into the policy…' :
            job.status === 'error' ? `Couldn't learn: ${job.error}` :
            `Done — cloned ${job.samples} winning moves into the policy (agents now use it).`}
          {job.history?.length > 0 && job.status !== 'error' && (
            <span className="mono"> · last epoch acc {Math.round((job.history.at(-1).accuracy || 0) * 100)}%</span>
          )}
        </div>
      )}

      {data.games?.length > 0 && (
        <table className="mini-table" style={{ marginTop: 14 }}>
          <thead><tr><th>Winner</th><th>Decks</th><th>Mode</th><th>Turns</th><th>Moves</th></tr></thead>
          <tbody>
            {data.games.slice(0, 8).map((g, i) => (
              <tr key={i}>
                <td>{g.winner_name}</td>
                <td className="mono">{g.deck_a} vs {g.deck_b}</td>
                <td>{g.mode}</td><td>{g.turns}</td><td>{g.samples}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function Lobby({ decks, onCreated, onJoined }) {
  const { favs } = useFavorites();
  const [form, setForm] = useState({ deck_a: '', deck_b: '', mode: 'async', turn_seconds: 90, name: '' });
  const [code, setCode] = useState('');
  const [joinName, setJoinName] = useState('');
  const [err, setErr] = useState('');
  const [open, setOpen] = useState([]);
  const openPoll = useRef(null);

  useEffect(() => {
    if (decks?.length) setForm((f) => ({ ...f, deck_a: f.deck_a || decks[0], deck_b: f.deck_b || decks[1] || decks[0] }));
  }, [decks]);

  const loadOpen = () => api.mpOpen().then((r) => setOpen(r.matches || [])).catch(() => {});
  useEffect(() => {
    loadOpen();
    openPoll.current = setInterval(loadOpen, 4000);
    return () => clearInterval(openPoll.current);
  }, []);

  async function create() {
    setErr('');
    try { onCreated(await api.mpCreate(form)); }
    catch (e) { setErr(e.message); }
  }
  async function join() {
    setErr('');
    if (!code.trim()) { setErr('Paste a match code to join.'); return; }
    try {
      const r = await api.mpJoin(code.trim(), joinName || 'Player 2');
      onJoined({ ...r, match_id: code.trim() });
    } catch (e) { setErr(e.message); }
  }
  async function quickJoin(mid) {
    setErr('');
    try {
      const r = await api.mpJoin(mid, joinName || 'Player 2');
      onJoined({ ...r, match_id: mid });
    } catch (e) { setErr(e.message); loadOpen(); }
  }

  return (
    <div className="mp-lobby">
      <div className="panel pad">
        <b style={{ fontFamily: 'var(--display)' }}>Host a match</b>
        <p className="sub" style={{ fontSize: 12.5, marginTop: 6 }}>Create a game and share the code with a friend. Two humans, masked hands, your choice of clock.</p>
        <div className="mp-form">
          <label className="field">Your name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Player 1" /></label>
          <label className="field">Your deck
            <select value={form.deck_a} onChange={(e) => setForm({ ...form, deck_a: e.target.value })}>
              {orderByFav(decks, favs.decks).map((d) => <option key={d} value={d}>{deckLabel(d, favs.decks)}</option>)}
            </select>
          </label>
          <label className="field">Opponent deck
            <select value={form.deck_b} onChange={(e) => setForm({ ...form, deck_b: e.target.value })}>
              {orderByFav(decks, favs.decks).map((d) => <option key={d} value={d}>{deckLabel(d, favs.decks)}</option>)}
            </select>
          </label>
          <label className="field">Turn style
            <select value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}>
              <option value="async">Send move &amp; wait (no clock)</option>
              <option value="timed">Timed turns</option>
            </select>
          </label>
          {form.mode === 'timed' && (
            <label className="field">Seconds / turn
              <input type="number" min="15" max="600" value={form.turn_seconds}
                onChange={(e) => setForm({ ...form, turn_seconds: Math.max(15, Math.min(600, +e.target.value || 90)) })} />
            </label>
          )}
        </div>
        <button className="btn primary" onClick={create} style={{ marginTop: 12 }}>Create match</button>
      </div>

      <div className="panel pad">
        <b style={{ fontFamily: 'var(--display)' }}>Join a match</b>
        <p className="sub" style={{ fontSize: 12.5, marginTop: 6 }}>Paste the code your opponent shared.</p>
        <label className="field" style={{ marginTop: 6 }}>Your name<input value={joinName} onChange={(e) => setJoinName(e.target.value)} placeholder="Player 2" /></label>
        <label className="field">Match code<input value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. de81c0a219" /></label>
        <button className="btn" onClick={join} style={{ marginTop: 12 }}>Join</button>

        <div style={{ marginTop: 18 }}>
          <div className="row between" style={{ alignItems: 'center' }}>
            <b style={{ fontFamily: 'var(--display)', fontSize: 14 }}>Open games</b>
            <span className="tag">{open.length}</span>
          </div>
          {open.length === 0
            ? <p className="sub" style={{ fontSize: 12, marginTop: 8 }}>No games waiting for a player right now. Host one on the left.</p>
            : (
              <div className="open-list" style={{ marginTop: 8 }}>
                {open.map((g) => (
                  <div key={g.match_id} className="open-row">
                    <div>
                      <div style={{ fontWeight: 600 }}>{g.host}</div>
                      <div className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>
                        {g.decks?.[0]} vs {g.decks?.[1]} · {g.mode === 'timed' ? `${g.turn_seconds}s/turn` : 'send & wait'}
                      </div>
                    </div>
                    <button className="btn primary sm" onClick={() => quickJoin(g.match_id)}>Join</button>
                  </div>
                ))}
              </div>
            )}
        </div>
      </div>

      {err && <div className="err" style={{ gridColumn: '1 / -1' }}>{err}</div>}
    </div>
  );
}

function Match({ match, onLeave, onRematch }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [localLeft, setLocalLeft] = useState(null);
  const [rematching, setRematching] = useState(false);
  const poll = useRef(null);
  const tick = useRef(null);

  async function refresh() {
    try {
      const s = await api.mpState(match.match_id, match.token);
      setData(s);
      setLocalLeft(s.time_left);
      setErr('');
    } catch (e) { setErr(e.message); }
  }

  useEffect(() => {
    refresh();
    poll.current = setInterval(refresh, 1500);
    return () => { clearInterval(poll.current); clearInterval(tick.current); };
  }, [match.match_id]);

  // smooth local countdown between polls (timed mode)
  useEffect(() => {
    clearInterval(tick.current);
    if (data?.mode === 'timed' && data?.time_left != null && !data.over) {
      tick.current = setInterval(() => setLocalLeft((t) => (t == null ? t : Math.max(0, +(t - 1).toFixed(0)))), 1000);
    }
    return () => clearInterval(tick.current);
  }, [data?.time_left, data?.over, data?.current_player]);

  async function act(index) {
    try { const s = await api.mpAction(match.match_id, match.token, index); setData(s); setLocalLeft(s.time_left); }
    catch (e) { setErr(e.message); refresh(); }
  }

  async function rematch() {
    setRematching(true);
    try {
      const info = await api.mpRematch(match.match_id, match.token);
      onRematch?.({ match_id: info.match_id, token: info.token, seat: info.seat });
    } catch (e) { setErr(e.message); setRematching(false); }
  }

  if (!data) return <div className="panel pad"><span className="live"><span className="spin" /> loading match…</span></div>;

  const seat = data.your_seat;
  const st = data.state;
  const me = st.players[seat];
  const opp = st.players[1 - seat];
  const waiting = data.status === 'waiting';
  const oppName = data.seats[String(1 - seat)]?.name;
  const myName = data.seats[String(seat)]?.name;

  return (
    <div>
      <div className="row between" style={{ marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <div className="row" style={{ gap: 8, alignItems: 'center' }}>
          <span className="pill">You: {myName} (seat {seat})</span>
          <span className="pill">vs {oppName || '…'}</span>
          <span className="pill">{data.mode === 'timed' ? 'Timed' : 'Send & wait'}</span>
          {!data.over && <span className="pill">Turn {st.turn_number}</span>}
        </div>
        <div className="row" style={{ gap: 8 }}>
          <span className="mono code-chip" title="Share this with your opponent">code: {match.match_id}</span>
          <button className="btn sm" onClick={onLeave}>Leave</button>
        </div>
      </div>

      {waiting && (
        <div className="panel pad" style={{ marginBottom: 12 }}>
          <span className="live"><span className="blip" /> Waiting for an opponent to join…</span>
          <p className="sub" style={{ fontSize: 12.5, marginTop: 8 }}>Share this match code: <b className="mono">{match.match_id}</b></p>
        </div>
      )}

      {data.over ? (
        <div className="panel pad win-banner" style={{ marginBottom: 12 }}>
          <span className="winner">{data.winner === seat ? 'You win! 🏆' : data.winner == null ? 'Draw' : `${oppName} wins`}</span>
          <span className="sub" style={{ marginLeft: 10, fontSize: 13, flex: 1 }}>
            {data.winner_samples ? `${data.winner_samples} winning moves captured — teach them to the agents below.` : ''}
          </span>
          <button className="btn primary sm" onClick={rematch} disabled={rematching}>
            {rematching ? <span className="spin" /> : 'Rematch (same decks)'}
          </button>
        </div>
      ) : !waiting && (
        <div className="panel pad turn-bar" style={{ marginBottom: 12 }}>
          <span className={`live ${data.your_turn ? 'you' : ''}`}>
            <span className="blip" /> {data.your_turn ? 'Your turn' : `Waiting for ${oppName}…`}
          </span>
          {data.mode === 'timed' && localLeft != null && (
            <span className={`clock ${localLeft <= 10 ? 'low' : ''}`}>⏱ {Math.ceil(localLeft)}s</span>
          )}
        </div>
      )}

      <ImageDisclaimer />
      <div className="arena" style={{ marginTop: 8 }}>
        <Board player={opp} activeTurn={!data.over && st.current_player === (1 - seat)} flip />
        <Board player={me} activeTurn={!data.over && st.current_player === seat} />
      </div>

      {data.your_turn && (
        <div className="panel pad" style={{ marginTop: 12 }}>
          <b style={{ fontFamily: 'var(--display)' }}>Your actions</b>
          <div className="tray" style={{ marginTop: 10 }}>
            {data.legal.map((a) => (
              <button key={a.index} className={`act-btn ${a.type === 'attack' ? 'attack' : ''} ${a.type === 'end_turn' ? 'end' : ''}`}
                onClick={() => act(a.index)}>{a.label}</button>
            ))}
          </div>
        </div>
      )}

      {err && <div className="err">{err}</div>}

      <div className="panel pad" style={{ marginTop: 12 }}>
        <b style={{ fontFamily: 'var(--display)' }}>Game log</b>
        <div className="log" style={{ marginTop: 8 }}>
          {(st.log || []).slice().reverse().map((l, i) => {
            const m = l.match(/^(T\d+:)\s*(.*)$/);
            return <div className="ln" key={i}>{m ? <><span className="t">{m[1]}</span>{m[2]}</> : l}</div>;
          })}
        </div>
      </div>
    </div>
  );
}

export default function Multiplayer() {
  const [decks, setDecks] = useState([]);
  const [match, setMatch] = useState(null);

  useEffect(() => {
    api.decks().then((r) => setDecks(r.decks)).catch(() => {});
    const saved = localStorage.getItem(MP_KEY);
    if (saved) { try { setMatch(JSON.parse(saved)); } catch {} }
  }, []);

  function enter(m) {
    const info = { match_id: m.match_id, token: m.token, seat: m.seat };
    localStorage.setItem(MP_KEY, JSON.stringify(info));
    setMatch(info);
  }
  function leave() {
    localStorage.removeItem(MP_KEY);
    setMatch(null);
  }

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Arena · Multiplayer</div>
        <h1>Two-player battles</h1>
        <p className="sub">Play a friend on the same authoritative engine — hands stay hidden per player. Choose a clock or play correspondence-style (send a move and wait). Every finished game teaches the agents the winner's strategy.</p>
      </div>

      {match
        ? <Match match={match} onLeave={leave} onRematch={enter} />
        : <Lobby decks={decks} onCreated={enter} onJoined={enter} />}

      <LearnedPanel />
    </div>
  );
}
