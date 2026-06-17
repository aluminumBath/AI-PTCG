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

export default function TrainingDashboard() {
  const [metrics, setMetrics] = useState(null);
  const [note, setNote] = useState('');
  const [auto, setAuto] = useState(true);

  async function load() {
    try {
      const r = await api.metrics();
      setMetrics(r.metrics || []);
      setNote(r.note || '');
    } catch (e) { setNote(String(e.message)); }
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
        <p className="sub">Live read-out from the PPO self-play trainer. Win rate is the trailing average against the current opponent; the policy improves as it learns to develop its board and time lethal attacks.</p>
      </div>

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
            <div className="panel stat"><div className="k">Win rate (trailing)</div><div className="v">{(last.winrate_recent * 100).toFixed(0)}<small>%</small></div></div>
            <div className="panel stat"><div className="k">Updates</div><div className="v">{last.update}</div></div>
            <div className="panel stat"><div className="k">Episodes</div><div className="v">{last.episodes}</div></div>
            <div className="panel stat"><div className="k">Opponent</div><div className="v" style={{ fontSize: 20 }}>{last.opponent}</div></div>
            <div className="panel stat"><div className="k">Entropy</div><div className="v">{last.entropy?.toFixed(2)}</div></div>
          </div>

          <div className="panel chart-wrap" style={{ marginBottom: 16 }}>
            <div className="row between"><b style={{ fontFamily: 'var(--display)' }}>Learning curve</b>
              <label className="row" style={{ gap: 6, fontSize: 12, color: 'var(--muted)' }}>
                <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} style={{ width: 'auto' }} /> auto-refresh
              </label>
            </div>
            <LineChart yMax={1} yLabel="win rate"
              series={[
                { name: 'recent', color: 'var(--grass)', points: metrics.map((m, i) => ({ x: i, y: m.winrate_recent })) },
                { name: 'per-update', color: 'var(--psychic)', points: metrics.map((m, i) => ({ x: i, y: m.winrate_update })) },
              ]} />
            <div className="chart-legend">
              <span><i style={{ background: 'var(--grass)' }} />Trailing win rate</span>
              <span><i style={{ background: 'var(--psychic)' }} />Per-update win rate</span>
            </div>
          </div>

          <div className="panel chart-wrap">
            <b style={{ fontFamily: 'var(--display)' }}>Value loss</b>
            <LineChart yMax={Math.max(...metrics.map((m) => m.value_loss), 0.5)} yLabel="MSE"
              series={[{ name: 'value', color: 'var(--water)', points: metrics.map((m, i) => ({ x: i, y: m.value_loss })) }]} />
          </div>
        </>
      )}
    </div>
  );
}
