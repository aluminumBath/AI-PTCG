import { useEffect, useState } from 'react';
import { api } from '../api';

function LineChart({ series, height = 240, yMax = 1, yLabel = '' }) {
  const W = 720, H = height, padL = 44, padB = 28, padT = 14, padR = 14;
  const all = series.flatMap((s) => s.points);
  const n = Math.max(...series.map((s) => s.points.length), 1);
  const xmax = Math.max(n - 1, 1);
  const ymax = yMax ?? Math.max(...all.map((p) => p.y), 1);
  const X = (i) => padL + (i / xmax) * (W - padL - padR);
  const Y = (v) => padT + (1 - v / ymax) * (H - padT - padB);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }}>
      {[0, 0.25, 0.5, 0.75, 1].map((g) => (
        <g key={g}>
          <line x1={padL} x2={W - padR} y1={Y(g * ymax)} y2={Y(g * ymax)} stroke="rgba(150,170,220,0.10)" />
          <text x={padL - 8} y={Y(g * ymax) + 4} fill="var(--faint)" fontSize="10" textAnchor="end" fontFamily="var(--mono)">
            {(g * ymax).toFixed(ymax <= 1 ? 2 : 0)}
          </text>
        </g>
      ))}
      <text x={padL} y={H - 8} fill="var(--faint)" fontSize="10" fontFamily="var(--mono)">update →</text>
      {yLabel && <text x={12} y={padT + 4} fill="var(--faint)" fontSize="10" fontFamily="var(--mono)">{yLabel}</text>}
      {series.map((s) => {
        if (s.points.length < 2) return null;
        const d = s.points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${X(p.x).toFixed(1)} ${Y(p.y).toFixed(1)}`).join(' ');
        return <path key={s.name} d={d} fill="none" stroke={s.color} strokeWidth="2.5" strokeLinejoin="round" />;
      })}
    </svg>
  );
}

function oppHealth(opp) {
  if (!opp || !opp.length) return { level: 'idle', label: 'Not trained', reason: 'run rl.opponent_model_train' };
  const last = opp[opp.length - 1];
  const hasVal = last.val_p_inhand != null;
  const inh = Number(hasVal ? last.val_p_inhand : last.p_inhand) || 0;
  const oth = Number(hasVal ? last.val_p_other : last.p_other) || 0;
  const sep = inh - oth;
  const green = sep >= 0.10;
  return {
    level: green ? 'green' : 'amber',
    label: green ? 'Reads opponent' : sep >= 0.04 ? 'Learning' : 'Near chance',
    reason: `Δ${sep.toFixed(2)} ${hasVal ? 'held-out' : 'train'} (in-hand ${inh.toFixed(2)} vs other ${oth.toFixed(2)})`,
  };
}

function policyHealth(metrics, polEval) {
  if (polEval && polEval.winrate != null) {
    const wr = Number(polEval.winrate);
    const green = wr >= 0.5;
    return {
      level: green ? 'green' : 'amber',
      label: green ? 'Beats heuristic' : 'Below heuristic',
      reason: `deployed ${polEval.agent} ${polEval.sims}-sim: ${Math.round(wr * 100)}% over ${polEval.games} games`,
    };
  }
  if (metrics && metrics.length) {
    const wrs = metrics.map((m) => Number(m.winrate_recent) || 0);
    const tail = wrs.slice(-15);
    const wr = tail.reduce((s, x) => s + x, 0) / tail.length;
    const peak = Math.max(...wrs);
    const green = wr >= 0.5;
    return {
      level: green ? 'green' : 'amber',
      label: green ? 'Beats heuristic' : 'Competitive',
      reason: `raw net ${Math.round(wr * 100)}% vs heuristic (peak ${Math.round(peak * 100)}%; deployed search stronger — run rl.eval_policy)`,
    };
  }
  return { level: 'idle', label: 'Not trained', reason: 'run rl.alphazero_train' };
}

export default function TrainingDashboard() {
  const [metrics, setMetrics] = useState(null);
  const [note, setNote] = useState('');
  const [err, setErr] = useState('');
  const [auto, setAuto] = useState(true);
  const [league, setLeague] = useState([]);
  const [opp, setOpp] = useState([]);
  const [polEval, setPolEval] = useState(null);

  async function load() {
    try {
      const r = await api.metrics();
      // keep only well-formed numeric rows so one bad entry can't break the view
      const clean = (r.metrics || []).filter((m) => Number.isFinite(Number(m.winrate_recent)));
      setMetrics(clean);
      setNote(r.note || '');
      setErr('');
    } catch (e) { setErr(String(e.message || e)); }
    try {
      const lg = await api.league();
      setLeague(lg.members || []);
    } catch { /* league is optional (only present during a --league run) */ }
    try {
      const om = await api.opponentMetrics();
      setOpp(om.metrics || []);
    } catch { /* opponent model is optional */ }
    try {
      const pe = await api.policyEval();
      setPolEval(pe && pe.winrate != null ? pe : null);
    } catch { /* deployed-agent eval is optional */ }
  }
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!auto) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [auto]);

  const last = metrics && metrics.length ? metrics[metrics.length - 1] : null;

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Mode · Training lab</div>
        <h1>Self-play training</h1>
        <p className="sub">Live read-out from the self-play trainers — PPO and AlphaZero (with the optional exploiter league) share the win-rate/value curves below, and the neural opponent model's training is shown at the bottom.</p>
      </div>

      {(() => {
        const palette = { green: '#5fbf78', amber: '#d9a441', idle: '#888' };
        const dots = [
          { name: 'Opponent model', h: oppHealth(opp) },
          { name: 'Policy', h: policyHealth(metrics || [], polEval) },
        ];
        return (
          <div className="row" style={{ gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
            {dots.map(({ name, h }) => {
              const c = palette[h.level];
              return (
                <div key={name} style={{ flex: '1 1 240px', minWidth: 210, border: `1px solid ${c}`,
                  borderRadius: 12, padding: '8px 12px', background: c + '14' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'var(--display)', fontSize: 13 }}>
                    <span style={{ width: 9, height: 9, borderRadius: 999, background: c, flex: '0 0 auto' }} />
                    {name}: <b style={{ color: c }}>{h.label}</b>
                  </div>
                  <div className="sub" style={{ fontSize: 11.5, marginTop: 3 }}>{h.reason}</div>
                </div>
              );
            })}
          </div>
        );
      })()}

      {err && <div className="err" style={{ marginBottom: 14 }}>Couldn't load training metrics: {err}</div>}

      {(!metrics || metrics.length === 0) ? (
        <div className="panel pad">
          <b style={{ fontFamily: 'var(--display)' }}>No training data yet</b>
          <p className="sub" style={{ marginTop: 8 }}>{note || 'Run the trainer to populate this dashboard.'}</p>
          <div className="hint" style={{ fontFamily: 'var(--mono)' }}>
            cd backend && python -m rl.train --updates 300 --episodes-per-update 16 --opponent self
          </div>
        </div>
      ) : (
        <>
          <div className="stat-grid" style={{ marginBottom: 16 }}>
            <div className="panel stat"><div className="k">Win rate (trailing)</div><div className="v">{((last.winrate_recent ?? 0) * 100).toFixed(0)}<small>%</small></div></div>
            <div className="panel stat"><div className="k">Updates</div><div className="v">{last.update ?? metrics.length}</div></div>
            <div className="panel stat"><div className="k">Episodes</div><div className="v">{last.episodes ?? '—'}</div></div>
            <div className="panel stat"><div className="k">Opponent</div><div className="v" style={{ fontSize: 20 }}>{last.opponent ?? '—'}</div></div>
            <div className="panel stat"><div className="k">Entropy</div><div className="v">{Number.isFinite(Number(last.entropy)) ? Number(last.entropy).toFixed(2) : '—'}</div></div>
          </div>

          <div className="panel chart-wrap" style={{ marginBottom: 16 }}>
            <div className="row between"><b style={{ fontFamily: 'var(--display)' }}>Learning curve</b>
              <label className="row" style={{ gap: 6, fontSize: 12, color: 'var(--muted)' }}>
                <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} style={{ width: 'auto' }} /> auto-refresh
              </label>
            </div>
            <LineChart yMax={1} yLabel="win rate"
              series={[
                { name: 'recent', color: 'var(--grass)', points: metrics.map((m, i) => ({ x: i, y: Number(m.winrate_recent) || 0 })) },
                { name: 'per-update', color: 'var(--psychic)', points: metrics.map((m, i) => ({ x: i, y: Number(m.winrate_update) || 0 })) },
              ]} />
            <div className="chart-legend">
              <span><i style={{ background: 'var(--grass)' }} />Trailing win rate</span>
              <span><i style={{ background: 'var(--psychic)' }} />Per-update win rate</span>
            </div>
          </div>

          <div className="panel chart-wrap">
            <b style={{ fontFamily: 'var(--display)' }}>Value loss</b>
            <LineChart yMax={Math.max(...metrics.map((m) => Number(m.value_loss) || 0), 0.5)} yLabel="MSE"
              series={[{ name: 'value', color: 'var(--water)', points: metrics.map((m, i) => ({ x: i, y: Number(m.value_loss) || 0 })) }]} />
          </div>

          {league.length > 0 && (
            <div className="panel pad" style={{ marginTop: 16 }}>
              <b style={{ fontFamily: 'var(--display)' }}>League standings</b>
              <p className="sub" style={{ marginTop: 6 }}>
                Opponents the learner trains against, ranked by how often they beat it — higher means a tougher exploiter the learner is being pushed to solve. Snapshots (<span style={{ fontFamily: 'var(--mono)' }}>snap*</span>) are frozen past versions of the learner.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
                {[...league].sort((a, b) => (b.beat_rate ?? -1) - (a.beat_rate ?? -1)).map((m) => {
                  const pct = m.beat_rate == null ? 0 : Math.round(m.beat_rate * 100);
                  return (
                    <div key={m.id} className="row" style={{ gap: 10, alignItems: 'center' }}>
                      <span style={{ width: 96, fontFamily: 'var(--mono)', fontSize: 13 }}>{m.id}</span>
                      <span className="tag" style={{ width: 64 }}>{m.kind}</span>
                      <div style={{ flex: 1, background: 'var(--panel-2, #1c1c22)', borderRadius: 6, height: 16, overflow: 'hidden' }}>
                        <div style={{ width: `${pct}%`, height: '100%',
                          background: pct >= 60 ? 'var(--fire, #e0533d)' : pct >= 40 ? 'var(--psychic, #b07bd4)' : 'var(--grass, #5fbf78)' }} />
                      </div>
                      <span style={{ width: 92, textAlign: 'right', fontSize: 12, color: 'var(--muted)' }}>
                        {m.beat_rate == null ? 'no games' : `${pct}% · ${m.games}g`}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {opp.length > 0 && (() => {
        const last = opp[opp.length - 1];
        const hasVal = last.val_p_inhand != null;
        const vIn = (m) => Number(hasVal ? m.val_p_inhand : m.p_inhand) || 0;
        const vOut = (m) => Number(hasVal ? m.val_p_other : m.p_other) || 0;
        const vAcc = (m) => Number(hasVal ? m.val_acc : m.acc) || 0;
        const sep = vIn(last) - vOut(last);
        return (
          <div className="panel chart-wrap" style={{ marginTop: 16 }}>
            <div className="row between">
              <b style={{ fontFamily: 'var(--display)' }}>Neural opponent model</b>
              <span className="sub" style={{ fontSize: 12 }}>
                {hasVal ? 'val' : 'train'} acc {Math.round(vAcc(last) * 100)}% · held-out Δ(in−out) {sep.toFixed(2)} · train acc {Math.round((Number(last.acc) || 0) * 100)}% · {last.samples} samples
              </span>
            </div>
            <p className="sub" style={{ marginTop: 4, marginBottom: 8 }}>
              Predicts which of the opponent's cards are in hand. The gap between the two held-out probability lines is the real signal (it drives belief-weighted ISMCTS and the Mind-reader); train-vs-val accuracy shows how well it generalises.
            </p>
            <LineChart yMax={1} yLabel="value"
              series={[
                { name: 'train acc', color: 'var(--muted, #888)', points: opp.map((m, i) => ({ x: i, y: Number(m.acc) || 0 })) },
                { name: 'val acc', color: 'var(--grass, #5fbf78)', points: opp.map((m, i) => ({ x: i, y: vAcc(m) })) },
                { name: 'P(in-hand)', color: 'var(--psychic, #b07bd4)', points: opp.map((m, i) => ({ x: i, y: vIn(m) })) },
                { name: 'P(other)', color: 'var(--water, #4ea3d9)', points: opp.map((m, i) => ({ x: i, y: vOut(m) })) },
              ]} />
            <div className="chart-legend">
              <span><i style={{ background: 'var(--muted, #888)' }} />Train acc</span>
              <span><i style={{ background: 'var(--grass, #5fbf78)' }} />Val acc (held-out)</span>
              <span><i style={{ background: 'var(--psychic, #b07bd4)' }} />P(in-hand)</span>
              <span><i style={{ background: 'var(--water, #4ea3d9)' }} />P(other)</span>
            </div>
            <div className="hint" style={{ fontFamily: 'var(--mono)', marginTop: 8 }}>
              cd backend && python -m rl.opponent_model_train --games 300 --epochs 4 --device mps
            </div>
          </div>
        );
      })()}
    </div>
  );
}
