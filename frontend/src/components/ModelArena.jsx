import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import Board from './Board';

const FAMILY_COLOR = {
  baseline: 'var(--metal)', 'rule-based': 'var(--lightning)',
  search: 'var(--water)', learned: 'var(--grass)', hybrid: 'var(--psychic)',
};

function Toggle({ on, onClick, children, color }) {
  return (
    <button className={`chip-toggle ${on ? 'on' : ''}`} onClick={onClick}
      style={on ? { borderColor: color || 'var(--accent)', color: 'var(--ink)' } : undefined}>
      <span className="chip-dot" style={{ background: on ? (color || 'var(--accent)') : 'transparent' }} />
      {children}
    </button>
  );
}

const ARENA_JOB_KEY = 'tcg.arena.job';

export default function ModelArena({ models, decks }) {
  const [picked, setPicked] = useState([]);
  const [pickedDecks, setPickedDecks] = useState([]);
  const [games, setGames] = useState(6);
  const [job, setJob] = useState(null);
  const [status, setStatus] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const [watch, setWatch] = useState(false);
  const watchRef = useRef(false);
  const poll = useRef(null);

  useEffect(() => { watchRef.current = watch; }, [watch]);

  useEffect(() => {
    if (models?.length && picked.length === 0) {
      setPicked(models.map((m) => m.id).filter((id) => id !== 'mcts' && id !== 'rl_mcts'));
    }
  }, [models]);
  useEffect(() => {
    if (decks?.length && pickedDecks.length === 0) setPickedDecks(decks.slice(0, 3));
  }, [decks]);

  function startPolling(jobId) {
    clearInterval(poll.current);
    const everyMs = watchRef.current ? 700 : 1200;  // livelier updates while watching
    poll.current = setInterval(async () => {
      try {
        const s = await api.tournamentStatus(jobId);
        setStatus(s);
        if (s.status !== 'running') {
          clearInterval(poll.current);
          setCancelling(false);
          localStorage.removeItem(ARENA_JOB_KEY);  // job is terminal; drop the handle
        }
      } catch (e) {
        clearInterval(poll.current);  // job gone (server restart) — stop and clear
        localStorage.removeItem(ARENA_JOB_KEY);
      }
    }, everyMs);
  }

  // re-arm polling at the faster cadence when the user starts watching mid-run
  useEffect(() => {
    if (job && status?.status === 'running') startPolling(job);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [watch]);

  // re-attach to a running/finished job after a tab switch or full refresh
  useEffect(() => {
    const saved = localStorage.getItem(ARENA_JOB_KEY);
    if (!saved) return;
    setJob(saved);
    api.tournamentStatus(saved).then((s) => {
      setStatus(s);
      if (s.status === 'running') startPolling(saved);
      else localStorage.removeItem(ARENA_JOB_KEY);
    }).catch(() => localStorage.removeItem(ARENA_JOB_KEY));
    return () => clearInterval(poll.current);
  }, []);

  async function stop() {
    if (!job) return;
    setCancelling(true);
    try { await api.cancelTournament(job); } catch (e) { setCancelling(false); }
  }

  const labelOf = (id) => models?.find((m) => m.id === id)?.label || id;
  const familyOf = (id) => models?.find((m) => m.id === id)?.family;

  function toggle(list, setList, id) {
    setList(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  }

  function randomizeDecks() {
    const all = decks || [];
    if (all.length < 2) { setPickedDecks([...all]); return; }
    const count = Math.min(all.length, 3 + Math.floor(Math.random() * 4)); // 3–6
    const shuffled = [...all].sort(() => Math.random() - 0.5);
    setPickedDecks(shuffled.slice(0, Math.max(2, count)));
  }

  async function run() {
    if (picked.length < 2 || pickedDecks.length === 0) return;
    setStatus(null);
    const r = await api.runTournament(picked, pickedDecks, games);
    setJob(r.job_id);
    localStorage.setItem(ARENA_JOB_KEY, r.job_id);  // survive tab switch / refresh
    setStatus({ status: 'running', done: 0, total: r.total_games });
    startPolling(r.job_id);
  }
  useEffect(() => () => clearInterval(poll.current), []);

  // Validation (CIs + sanity checks) auto-loads when a result is available.
  const [val, setVal] = useState(null);
  useEffect(() => {
    if (status?.status === 'done' || status?.status === 'cancelled') {
      api.tournamentValidate(job).then(setVal).catch(() => setVal(null));
    } else {
      setVal(null);
    }
  }, [job, status?.status]);
  const ciFor = (agent) => val?.winrates?.[agent]?.overall || null;
  const STATUS_DOT = { pass: 'var(--ok, #45c86b)', info: 'var(--muted)', warn: 'var(--warn, #e0a84e)' };
  const result = (status?.status === 'done' || status?.status === 'cancelled') ? status.result : null;
  const running = status?.status === 'running';
  const pct = status?.total ? Math.round((status.done / status.total) * 100) : 0;
  const hasSlow = picked.some((id) => ['mcts', 'rl_mcts', 'ismcts', 'flat_mc', 'council', 'prime', 'meta_top3'].includes(id));

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Intelligence · Compare</div>
        <h1>Model arena</h1>
        <p className="sub">Run a round-robin between models across your decks to see which makes the strongest opponent. Sides and deck matchups are alternated for fairness; results are ranked by win rate with a head-to-head matrix below.</p>
      </div>

      <div className="panel pad" style={{ marginBottom: 16 }}>
        <div className="nav-label" style={{ padding: '0 0 8px' }}>Models</div>
        <div className="chips">
          {(models || []).map((m) => (
            <Toggle key={m.id} on={picked.includes(m.id)} color={FAMILY_COLOR[m.family]}
              onClick={() => toggle(picked, setPicked, m.id)}>
              {m.label}<span className="chip-fam">{m.family}</span>
            </Toggle>
          ))}
        </div>

        <div className="row between" style={{ padding: '16px 0 8px', alignItems: 'center' }}>
          <div className="nav-label" style={{ padding: 0 }}>Decks (your dataset)</div>
          <div className="row" style={{ gap: 6 }}>
            <button type="button" className="btn sm" onClick={randomizeDecks}>🎲 Randomize</button>
            <button type="button" className="btn sm" onClick={() => setPickedDecks([...(decks || [])])}>All</button>
            <button type="button" className="btn sm" onClick={() => setPickedDecks([])}>Clear</button>
          </div>
        </div>
        <div className="chips">
          {(decks || []).map((d) => (
            <Toggle key={d} on={pickedDecks.includes(d)} onClick={() => toggle(pickedDecks, setPickedDecks, d)}>
              {d}
            </Toggle>
          ))}
        </div>

        <div className="row" style={{ marginTop: 18 }}>
          <label className="field">Games per pairing
            <input type="number" min="1" max="30" value={games}
              onChange={(e) => setGames(Math.max(1, Math.min(30, +e.target.value || 1)))} style={{ width: 90 }} />
          </label>
          <div className="grow" />
          {running && (
            <button className="btn danger" onClick={stop} disabled={cancelling} style={{ alignSelf: 'end', marginRight: 8 }}>
              {cancelling ? 'Stopping…' : 'Stop'}
            </button>
          )}
          <button className="btn primary" onClick={run} disabled={running || picked.length < 2 || pickedDecks.length === 0} style={{ alignSelf: 'end' }}>
            {running ? <span className="spin" /> : 'Run tournament'}
          </button>
        </div>
        {hasSlow && <p className="sub" style={{ marginTop: 10, fontSize: 12 }}>Heads up: the search-heavy and ensemble models (MCTS, ISMCTS, RL+MCTS, Council, Prime, Meta) run several seconds per move, so tournaments including them take noticeably longer.</p>}
      </div>

      {running && (
        <div className="panel pad" style={{ marginBottom: 16 }}>
          <div className="row between" style={{ marginBottom: 8 }}>
            <span className="live"><span className="blip" /> playing matches…</span>
            <div className="row" style={{ gap: 8, alignItems: 'center' }}>
              <button className={`btn sm ${watch ? 'primary' : ''}`} onClick={() => setWatch((w) => !w)}>
                {watch ? 'Hide battle' : '👁 Watch battle'}
              </button>
              <span className="tag">{status.done} / {status.total} games</span>
            </div>
          </div>
          <div className="bar"><div className="bar-fill" style={{ width: `${pct}%` }} /></div>
          <p className="sub" style={{ marginTop: 8, fontSize: 12 }}>This runs on the server — you can switch tabs or refresh and it keeps going. Use Stop to end it early (partial results are kept).</p>
        </div>
      )}

      {running && watch && (
        status?.current ? (
          <div className="panel pad" style={{ marginBottom: 16 }}>
            <div className="row between" style={{ marginBottom: 6 }}>
              <span className="live you"><span className="blip" /> Live · game {status.current.game_no} / {status.current.total_games}</span>
              <span className="tag">Turn {status.current.turn}</span>
            </div>
            <div className="row between" style={{ marginBottom: 10, fontSize: 12.5, flexWrap: 'wrap', gap: 6 }}>
              <span><b>{labelOf(status.current.seat0_agent)}</b> <span className="mono" style={{ color: 'var(--muted)' }}>· {status.current.deck0}</span></span>
              <span style={{ color: 'var(--faint)' }}>vs</span>
              <span><b>{labelOf(status.current.seat1_agent)}</b> <span className="mono" style={{ color: 'var(--muted)' }}>· {status.current.deck1}</span></span>
            </div>
            <div className="arena">
              <Board player={status.current.state.players[1]} activeTurn={status.current.state.current_player === 1} flip />
              <Board player={status.current.state.players[0]} activeTurn={status.current.state.current_player === 0} />
            </div>
            {status.current.rationale && (
              <div className="panel pad" style={{ marginTop: 10, fontSize: 12.5 }}>
                <b>{labelOf(status.current.mover_agent) || 'Move'}:</b> {status.current.rationale}
              </div>
            )}
            <div className="log" style={{ marginTop: 10, maxHeight: 170 }}>
              {(status.current.state.log || []).slice().reverse().map((l, i) => {
                const m = l.match(/^(T\d+:)\s*(.*)$/);
                return <div className="ln" key={i}>{m ? <><span className="t">{m[1]}</span>{m[2]}</> : l}</div>;
              })}
            </div>
          </div>
        ) : (
          <div className="panel pad" style={{ marginBottom: 16 }}>
            <span className="sub" style={{ fontSize: 13 }}>Loading the current battle… (search-heavy models think for a few seconds per move)</span>
          </div>
        )
      )}

      {status?.status === 'cancelled' && (
        <div className="panel pad" style={{ marginBottom: 16 }}>
          <span className="tag warn">Stopped</span>
          <span className="sub" style={{ marginLeft: 8, fontSize: 13 }}>
            Tournament stopped after {result?.games_played ?? 0} of {result?.total_games ?? 0} games — partial standings below.
          </span>
        </div>
      )}

      {status?.status === 'error' && <div className="err">{status.error}</div>}

      {result && (
        <>
          <div className="banner" style={{ marginBottom: 16 }}>
            <span className="winner">Best opponent: {labelOf(result.best)}</span>
            <p className="sub" style={{ marginTop: 4 }}>{result.total_games} games · {result.games_per_pairing} per pairing · {result.decks.length} decks</p>
          </div>

          <div className="panel pad" style={{ marginBottom: 16 }}>
            <b style={{ fontFamily: 'var(--display)' }}>Standings</b>
            <table className="tbl" style={{ marginTop: 10 }}>
              <thead><tr><th>#</th><th>Model</th><th>Win rate</th><th>W / L / D</th><th>Avg turns</th></tr></thead>
              <tbody>
                {result.standings.map((r, i) => (
                  <tr key={r.agent}>
                    <td style={{ fontFamily: 'var(--mono)' }}>{i + 1}</td>
                    <td>
                      <span className="chip-dot" style={{ background: FAMILY_COLOR[familyOf(r.agent)], display: 'inline-block', marginRight: 8 }} />
                      {labelOf(r.agent)}{i === 0 && <span className="pill" style={{ marginLeft: 8 }}>best</span>}
                    </td>
                    <td style={{ minWidth: 180 }}>
                      <div className="row" style={{ gap: 8 }}>
                        <div className="bar" style={{ flex: 1 }}><div className="bar-fill" style={{ width: `${r.winrate * 100}%`, background: FAMILY_COLOR[familyOf(r.agent)] }} /></div>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{(r.winrate * 100).toFixed(0)}%</span>
                      </div>
                      {ciFor(r.agent) && (
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--faint)', marginTop: 3 }}>
                          95% CI {Math.round(ciFor(r.agent).ci_lo * 100)}–{Math.round(ciFor(r.agent).ci_hi * 100)}% · ±{Math.round(ciFor(r.agent).ci_half * 100)}
                        </div>
                      )}
                    </td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{r.wins} / {r.losses} / {r.draws}</td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{r.avg_turns}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="panel pad">
            <b style={{ fontFamily: 'var(--display)' }}>Head-to-head</b>
            <p className="sub" style={{ fontSize: 12, marginTop: 2 }}>Wins for the row model against the column model.</p>
            <div style={{ overflowX: 'auto', marginTop: 10 }}>
              <table className="tbl matrix">
                <thead><tr><th></th>{result.agents.map((c) => <th key={c}>{labelOf(c)}</th>)}</tr></thead>
                <tbody>
                  {result.agents.map((rw) => (
                    <tr key={rw}>
                      <th>{labelOf(rw)}</th>
                      {result.agents.map((c) => {
                        const v = result.matrix[rw][c];
                        const tot = v + result.matrix[c][rw];
                        const intensity = tot ? v / tot : 0;
                        return (
                          <td key={c} style={{ textAlign: 'center', fontFamily: 'var(--mono)',
                            background: rw === c ? 'transparent' : `rgba(69,200,107,${0.08 + intensity * 0.4})`,
                            color: rw === c ? 'var(--faint)' : 'var(--ink)' }}>
                            {rw === c ? '—' : v}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {val && (
            <div className="panel pad" style={{ marginTop: 16 }}>
              <div className="row between">
                <b style={{ fontFamily: 'var(--display)' }}>Diagnostics — confidence &amp; sanity checks</b>
                <span className="tag" style={{ background: STATUS_DOT[val.verdict], color: '#0a0e1f' }}>
                  {val.verdict === 'pass' ? 'looks solid' : val.verdict === 'warn' ? 'needs care' : 'ok, with notes'}
                </span>
              </div>
              <p className="sub" style={{ fontSize: 12, marginTop: 4 }}>
                Win rates are estimates from a finite number of games; the 95% interval is the plausible range.
                A wide interval means run more games before trusting the order.
              </p>
              <div style={{ marginTop: 10 }}>
                {val.checks.map((c) => (
                  <div key={c.id} className="rule">
                    <div className="rule-name">
                      <span style={{ color: STATUS_DOT[c.status] }}>{c.status === 'pass' ? '✓' : c.status === 'warn' ? '!' : 'ℹ'}</span>
                      {c.label}
                      <span className="tag" style={{ marginLeft: 8 }}>{c.status}</span>
                    </div>
                    <div className="rule-detail">{c.detail}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <ConsistencyPanel models={models} pickedDecks={pickedDecks} decks={decks}
            defaultA={result.best} labelOf={labelOf} />
        </>
      )}
    </div>
  );
}

// Repeated independent batches of one matchup -> mean ± standard deviation, with
// a small per-batch bar chart. Runs as its own background job.
function ConsistencyPanel({ models, pickedDecks, decks, defaultA, labelOf }) {
  const list = models && models.length ? models : [{ id: 'heuristic', label: 'Heuristic' }, { id: 'random', label: 'Random' }];
  const [a, setA] = useState(defaultA || list[0]?.id || 'heuristic');
  const [b, setB] = useState('random');
  const [batches, setBatches] = useState(5);
  const [gpb, setGpb] = useState(20);
  const [job, setJob] = useState(null);
  const [status, setStatus] = useState(null);
  const poll = useRef(null);

  const usingDecks = (pickedDecks && pickedDecks.length ? pickedDecks : (decks || []).slice(0, 2));
  const running = status?.status === 'running';
  const res = status?.status === 'done' || status?.status === 'cancelled' ? status.result : null;

  function startPolling(id) {
    clearInterval(poll.current);
    poll.current = setInterval(async () => {
      try {
        const s = await api.consistencyStatus(id);
        setStatus(s);
        if (s.status !== 'running') clearInterval(poll.current);
      } catch { /* transient */ }
    }, 800);
  }
  useEffect(() => () => clearInterval(poll.current), []);

  async function run() {
    setStatus({ status: 'running', done: 0, total: batches * gpb });
    try {
      const r = await api.consistencyRun({ agent_a: a, agent_b: b, decks: usingDecks, batches, games_per_batch: gpb });
      setJob(r.job_id); startPolling(r.job_id);
    } catch (e) { setStatus({ status: 'error', error: e.message }); }
  }
  async function stop() { if (job) { try { await api.cancelConsistency(job); } catch { /* ignore */ } } }

  const rates = res ? res.per_batch.map((x) => x.winrate).filter((x) => x != null) : [];
  const pct = status?.total ? Math.round((status.done / status.total) * 100) : 0;

  return (
    <div className="panel pad" style={{ marginTop: 16 }}>
      <b style={{ fontFamily: 'var(--display)' }}>Consistency check (mean ± SD)</b>
      <p className="sub" style={{ fontSize: 12, marginTop: 2 }}>
        Replays one matchup over several independent seeded batches to see how much the win rate swings run-to-run.
        {usingDecks.length ? ` Decks: ${usingDecks.join(', ')}.` : ''}
      </p>
      <div className="row" style={{ gap: 12, flexWrap: 'wrap', marginTop: 8, alignItems: 'flex-end' }}>
        <label className="field">Model A
          <select value={a} onChange={(e) => setA(e.target.value)}>
            {list.map((m) => <option key={m.id} value={m.id}>{m.label || m.id}</option>)}
          </select>
        </label>
        <label className="field">vs Model B
          <select value={b} onChange={(e) => setB(e.target.value)}>
            {list.map((m) => <option key={m.id} value={m.id}>{m.label || m.id}</option>)}
          </select>
        </label>
        <label className="field">Batches
          <input type="number" min="2" max="20" value={batches} onChange={(e) => setBatches(Math.max(2, Math.min(20, +e.target.value || 2)))} style={{ width: 80 }} />
        </label>
        <label className="field">Games / batch
          <input type="number" min="2" max="50" value={gpb} onChange={(e) => setGpb(Math.max(2, Math.min(50, +e.target.value || 2)))} style={{ width: 90 }} />
        </label>
        <div className="grow" />
        {running && <button className="btn danger sm" onClick={stop} style={{ alignSelf: 'end' }}>Stop</button>}
        <button className="btn primary" onClick={run} disabled={running || a === b} style={{ alignSelf: 'end' }}>
          {running ? <span className="spin" /> : 'Run consistency check'}
        </button>
      </div>
      {a === b && <p className="sub" style={{ fontSize: 12, marginTop: 8 }}>Pick two different models.</p>}

      {running && (
        <div style={{ marginTop: 12 }}>
          <div className="bar"><div className="bar-fill" style={{ width: `${pct}%` }} /></div>
          <p className="sub" style={{ fontSize: 12, marginTop: 6 }}>Playing batches… {status.done}/{status.total} games.</p>
        </div>
      )}
      {status?.status === 'error' && <div className="err" style={{ marginTop: 10 }}>{status.error}</div>}

      {res && (
        <div style={{ marginTop: 14 }}>
          <div className="row" style={{ gap: 18, flexWrap: 'wrap', alignItems: 'baseline' }}>
            <span style={{ fontFamily: 'var(--display)', fontSize: 18 }}>
              {labelOf ? labelOf(res.agent_a) : res.agent_a}: {(res.mean * 100).toFixed(0)}%
              <span style={{ color: 'var(--muted)', fontSize: 13 }}> mean</span>
              <span style={{ color: 'var(--accent)', fontSize: 15 }}> ± {(res.std * 100).toFixed(0)}%</span>
              <span style={{ color: 'var(--muted)', fontSize: 13 }}> SD</span>
            </span>
            <span className="tag">pooled {(res.pooled_winrate * 100).toFixed(0)}% · 95% CI {Math.round(res.ci_lo * 100)}–{Math.round(res.ci_hi * 100)}%</span>
            <span className="tag">{res.decided} decided</span>
          </div>
          <p className="sub" style={{ fontSize: 12, marginTop: 6 }}>{res.note} <span style={{ color: 'var(--faint)' }}>(vs {labelOf ? labelOf(res.agent_b) : res.agent_b})</span></p>

          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 120, marginTop: 12,
            padding: '0 4px', borderBottom: '1px solid var(--line)', position: 'relative' }}>
            {/* mean line */}
            <div style={{ position: 'absolute', left: 0, right: 0, bottom: `${res.mean * 100}%`, borderTop: '1px dashed var(--accent)' }} />
            {rates.map((wr, i) => (
              <div key={i} title={`Batch ${i + 1}: ${(wr * 100).toFixed(0)}%`}
                style={{ flex: 1, height: `${Math.max(2, wr * 100)}%`, background: 'var(--accent-soft)',
                  borderTop: '2px solid var(--accent)', borderRadius: '3px 3px 0 0' }} />
            ))}
          </div>
          <div className="row between" style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--faint)', marginTop: 4 }}>
            <span>batch 1</span><span>per-batch win rate · dashed = mean</span><span>batch {rates.length}</span>
          </div>
        </div>
      )}
    </div>
  );
}
