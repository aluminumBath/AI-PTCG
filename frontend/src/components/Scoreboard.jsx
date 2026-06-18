import { useEffect, useState } from 'react';
import { api } from '../api';
import ModelInfoModal from './ModelInfoModal';

export default function Scoreboard() {
  const [docs, setDocs] = useState([]);
  const [statsById, setStatsById] = useState({});
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null);

  async function refresh() {
    setLoading(true);
    const [d, s] = await Promise.all([api.modelDocs(), api.modelStats()]);
    setDocs(d.models || []);
    const map = {}; (s.stats || []).forEach((r) => { map[r.model_id] = r; });
    setStatsById(map);
    setLoading(false);
  }
  useEffect(() => { refresh(); }, []);

  // every model is listed (played or not); rank by win rate then games
  const rows = docs.map((m) => ({ ...m, stat: statsById[m.id] || null }))
    .sort((a, b) => {
      const wa = a.stat?.win_rate ?? -1, wb = b.stat?.win_rate ?? -1;
      if (wb !== wa) return wb - wa;
      return (b.stat?.games ?? 0) - (a.stat?.games ?? 0);
    });
  const totalGames = Object.values(statsById).reduce((s, r) => s + r.games, 0);

  function dl(obj, name) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
  }
  async function exportAll() { dl(await api.modelsExportAll(), 'all-models.json'); }
  async function exportOne(id) { dl(await api.modelExport(id), `model-${id}.json`); }
  function exportScoresCSV() {
    const head = 'model_id,label,family,games,wins,losses,draws,win_rate,points,points_per_game';
    const body = rows.filter((r) => r.stat).map((r) => {
      const s = r.stat;
      return `${r.id},"${r.label}",${r.family},${s.games},${s.wins},${s.losses},${s.draws},${s.win_rate},${s.points},${s.points_per_game}`;
    });
    const url = URL.createObjectURL(new Blob([[head, ...body].join('\n') + '\n'], { type: 'text/csv' }));
    const a = document.createElement('a'); a.href = url; a.download = 'model_scores.csv'; a.click();
    URL.revokeObjectURL(url);
  }
  async function reset() {
    if (!window.confirm('Reset all lifetime model scores?')) return;
    await api.modelStatsReset(); refresh();
  }

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Intelligence · Models</div>
        <h1>Models &amp; scoreboard</h1>
        <p className="sub">Every agent, with its lifetime win/loss record across <b>all</b> games (Watch, Play vs AI, Model Arena, ladder episodes). Click a model for a full explanation of how it works and why it was chosen, or export any model in one click.</p>
      </div>

      <div className="row between" style={{ marginBottom: 14 }}>
        <div className="row" style={{ gap: 10 }}>
          <span className="pill">{docs.length} models</span>
          <span className="tag">{totalGames} games recorded</span>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn primary sm" onClick={exportAll}>Export all models</button>
          <button className="btn sm" onClick={exportScoresCSV} disabled={!totalGames}>Scores CSV</button>
          <button className="btn ghost sm" onClick={refresh}>Refresh</button>
          <button className="btn ghost sm danger" onClick={reset} disabled={!totalGames}>Reset scores</button>
        </div>
      </div>

      <div className="panel">
        <table className="tbl">
          <thead><tr>
            <th>Model</th><th>Family</th><th>Games</th><th>W / L / D</th>
            <th>Win rate</th><th>Points</th><th></th>
          </tr></thead>
          <tbody>
            {rows.map((r) => {
              const s = r.stat;
              return (
                <tr key={r.id} className="clickable" onClick={() => setModal(r)}>
                  <td><b>{r.label}</b></td>
                  <td><span className="tag">{r.family}</span></td>
                  <td className="mono">{s ? s.games : 0}</td>
                  <td className="mono">{s ? `${s.wins}/${s.losses}/${s.draws}` : '—'}</td>
                  <td>
                    {s ? <>
                      <div className="mono">{(s.win_rate * 100).toFixed(0)}%</div>
                      <div className="winbar"><div style={{ width: `${s.win_rate * 100}%` }} /></div>
                    </> : <span className="sub">no games</span>}
                  </td>
                  <td className="mono">{s ? s.points : 0}</td>
                  <td className="row" style={{ gap: 6, justifyContent: 'flex-end' }} onClick={(e) => e.stopPropagation()}>
                    <button className="btn ghost xs" onClick={() => setModal(r)}>ⓘ info</button>
                    <button className="btn ghost xs" onClick={() => exportOne(r.id)}>export</button>
                  </td>
                </tr>
              );
            })}
            {loading && <tr><td colSpan="7" className="sub" style={{ padding: 18 }}><span className="spin" /> loading…</td></tr>}
          </tbody>
        </table>
      </div>

      <ModelInfoModal model={modal} onClose={() => setModal(null)} />
    </div>
  );
}
