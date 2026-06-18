import { useEffect, useRef, useState } from 'react';
import { api } from '../api';

const LINE = ['#4ea1ff', '#ff7a59', '#39d98a', '#c792ea', '#ffd166', '#f78fb3', '#5ad1cd'];
const EP_JOB_KEY = 'tcg.ladder.episodeJob';

function RatingChart({ series }) {
  // series: [{name, color, points:[{games,mu,sigma}]}]
  const W = 720, H = 260, P = 34;
  const all = series.flatMap((s) => s.points);
  if (all.length === 0) return <div className="sub">Run episodes to see rating progress.</div>;
  const maxG = Math.max(4, ...all.map((p) => p.games));
  const muHi = Math.max(...all.map((p) => p.mu + p.sigma), 850);
  const muLo = Math.min(...all.map((p) => p.mu - p.sigma), 350);
  const x = (g) => P + (g / maxG) * (W - P * 2);
  const y = (m) => H - P - ((m - muLo) / (muHi - muLo)) * (H - P * 2);
  const ticks = [muLo, (muLo + muHi) / 2, muHi].map(Math.round);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" preserveAspectRatio="xMidYMid meet">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={P} y1={y(t)} x2={W - P} y2={y(t)} stroke="rgba(255,255,255,.06)" />
          <text x={8} y={y(t) + 3} fill="var(--faint)" fontSize="10" fontFamily="var(--mono)">{t}</text>
        </g>
      ))}
      <text x={W / 2} y={H - 6} fill="var(--faint)" fontSize="10" textAnchor="middle" fontFamily="var(--mono)">games played →</text>
      {series.map((s) => {
        if (s.points.length === 0) return null;
        const band = s.points.map((p) => `${x(p.games)},${y(p.mu + p.sigma)}`)
          .concat(s.points.slice().reverse().map((p) => `${x(p.games)},${y(p.mu - p.sigma)}`)).join(' ');
        const line = s.points.map((p, i) => `${i ? 'L' : 'M'}${x(p.games)},${y(p.mu)}`).join(' ');
        return (
          <g key={s.name}>
            <polygon points={band} fill={s.color} opacity="0.08" />
            <path d={line} fill="none" stroke={s.color} strokeWidth="2" />
            {s.points.slice(-1).map((p) => (
              <circle key="end" cx={x(p.games)} cy={y(p.mu)} r="3" fill={s.color} />
            ))}
          </g>
        );
      })}
    </svg>
  );
}

export default function Submissions() {
  const [subs, setSubs] = useState([]);
  const [maxActive, setMaxActive] = useState(10);
  const [models, setModels] = useState([]);
  const [decks, setDecks] = useState([]);
  const [series, setSeries] = useState([]);
  const [form, setForm] = useState({ name: '', agent: '', deck: 'rotating' });
  const [run, setRun] = useState(null);
  const [epJob, setEpJob] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const [err, setErr] = useState('');
  const [openLog, setOpenLog] = useState(null);
  const poll = useRef(null);     // submission validation polling
  const epPoll = useRef(null);   // episode-run polling (independent lifecycle)

  async function refresh() {
    const r = await api.submissionsList();
    setSubs(r.submissions); setMaxActive(r.max_active);
    const active = r.submissions.filter((s) => s.status === 'active');
    const details = await Promise.all(active.map((s) => api.submissionDetail(s.id).catch(() => null)));
    setSeries(details.filter(Boolean).map((d, i) => ({
      name: d.name, color: LINE[i % LINE.length], points: d.history || [],
    })));
  }

  useEffect(() => {
    refresh();
    api.agents().then((r) => {
      setModels(r.models);
      setForm((f) => ({ ...f, agent: r.models[1]?.id || r.models[0]?.id || '' }));
    });
    api.decks().then((r) => setDecks(r.decks));
    // re-attach to a running/finished episode job after a tab switch or refresh
    const saved = localStorage.getItem(EP_JOB_KEY);
    if (saved) {
      setEpJob(saved);
      api.episodeStatus(saved).then((st) => {
        setRun(st);
        if (st.status === 'running') startEpisodePolling(saved);
        else localStorage.removeItem(EP_JOB_KEY);
      }).catch(() => localStorage.removeItem(EP_JOB_KEY));
    }
    return () => { clearInterval(poll.current); clearInterval(epPoll.current); };
  }, []);

  function startEpisodePolling(jobId) {
    clearInterval(epPoll.current);
    epPoll.current = setInterval(async () => {
      try {
        const st = await api.episodeStatus(jobId);
        setRun(st);
        refresh();
        if (st.status !== 'running') {
          clearInterval(epPoll.current);
          setCancelling(false);
          localStorage.removeItem(EP_JOB_KEY);
        }
      } catch (e) {
        clearInterval(epPoll.current);
        localStorage.removeItem(EP_JOB_KEY);
      }
    }, 1500);
  }

  async function stopEpisodes() {
    if (!epJob) return;
    setCancelling(true);
    try { await api.cancelEpisodes(epJob); } catch (e) { setCancelling(false); }
  }

  async function submit() {
    setErr('');
    if (!form.name.trim()) { setErr('Give your submission a name.'); return; }
    try {
      await api.createSubmission(form);
      setForm((f) => ({ ...f, name: '' }));
      refresh();
      // poll while it validates
      clearInterval(poll.current);
      poll.current = setInterval(refresh, 2500);
      setTimeout(() => clearInterval(poll.current), 60000);
    } catch (e) { setErr(e.message); }
  }

  async function startRun() {
    setErr('');
    try {
      const { job_id } = await api.runEpisodes(40);
      setEpJob(job_id);
      localStorage.setItem(EP_JOB_KEY, job_id);  // survive tab switch / refresh
      setRun({ status: 'running', progress: 0, total: 40 });
      startEpisodePolling(job_id);
    } catch (e) { setErr(e.message); }
  }

  async function doExport(id) {
    const m = await api.submissionExport(id);
    const blob = new Blob([JSON.stringify(m, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `submission-${m.submission}.json`; a.click();
    URL.revokeObjectURL(url);
  }

  async function remove(id) {
    await api.deleteSubmission(id); refresh();
  }

  const activeCount = subs.filter((s) => s.status !== 'error').length;

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Ladder · Submissions</div>
        <h1>Skill-rating ladder</h1>
        <p className="sub">Each submission is an AI agent rated by a Gaussian N(μ, σ²) — μ is skill, σ is uncertainty that shrinks with games. New submissions self-validate (mirror match) before joining, then play rating-matched episodes on rotating decks. Ranked by the conservative score μ − 3σ.</p>
      </div>

      {err && <div className="err">{err}</div>}

      <div className="row" style={{ gap: 16, alignItems: 'stretch', marginBottom: 16 }}>
        <div className="panel pad" style={{ flex: '1 1 340px' }}>
          <b style={{ fontFamily: 'var(--display)' }}>New submission</b>
          <div className="sub" style={{ fontSize: 12, margin: '4px 0 12px' }}>{activeCount}/{maxActive} slots used</div>
          <input className="input" placeholder="Submission name" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })} style={{ marginBottom: 8 }} />
          <div className="row" style={{ gap: 8 }}>
            <select className="input" value={form.agent} onChange={(e) => setForm({ ...form, agent: e.target.value })}>
              {models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
            <select className="input" value={form.deck} onChange={(e) => setForm({ ...form, deck: e.target.value })}>
              <option value="rotating">Rotating decks</option>
              {decks.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <button className="btn primary" style={{ marginTop: 12, width: '100%' }}
            onClick={submit} disabled={activeCount >= maxActive}>Submit & validate</button>
        </div>

        <div className="panel pad" style={{ flex: '1 1 340px' }}>
          <div className="row between">
            <b style={{ fontFamily: 'var(--display)' }}>Run episodes</b>
            <button className="btn primary sm" onClick={startRun}
              disabled={run?.status === 'running' || subs.filter((s) => s.status === 'active').length < 2}>
              {run?.status === 'running' ? <span className="spin" /> : 'Run 40 episodes'}
            </button>
            {run?.status === 'running' && (
              <button className="btn danger sm" onClick={stopEpisodes} disabled={cancelling} style={{ marginLeft: 8 }}>
                {cancelling ? 'Stopping…' : 'Stop'}
              </button>
            )}
          </div>
          <p className="sub" style={{ fontSize: 12, marginTop: 8 }}>Pairs submissions with similar ratings; newer agents play more often for faster feedback.</p>
          {run && (
            <div style={{ marginTop: 10 }}>
              <div className="bar"><div className="bar-fill" style={{ width: `${(100 * (run.progress || 0)) / (run.total || 1)}%` }} /></div>
              <div className="sub" style={{ fontSize: 12, marginTop: 6 }}>
                {run.status === 'running' ? `Playing… ${run.progress}/${run.total} — runs on the server; you can switch tabs or refresh.` :
                  run.status === 'error' ? `Error: ${run.error}` :
                  run.status === 'cancelled' ? `Stopped after ${run.progress} episodes (ratings kept).` :
                  `Done — ${run.progress} episodes played`}
              </div>
            </div>
          )}
          {subs.filter((s) => s.status === 'active').length < 2 &&
            <p className="sub" style={{ fontSize: 12, marginTop: 8 }}>Need at least 2 active submissions.</p>}
        </div>
      </div>

      <div className="panel pad" style={{ marginBottom: 16 }}>
        <b style={{ fontFamily: 'var(--display)' }}>Rating progress</b>
        <div className="row" style={{ gap: 12, flexWrap: 'wrap', margin: '8px 0' }}>
          {series.map((s) => (
            <span key={s.name} className="legend"><i style={{ background: s.color }} />{s.name}</span>
          ))}
        </div>
        <RatingChart series={series} />
      </div>

      <div className="panel">
        <table className="tbl">
          <thead><tr>
            <th>Submission</th><th>Model</th><th>Skill (μ ± σ)</th><th>μ − 3σ</th>
            <th>W / L / D</th><th>Games</th><th>Status</th><th></th>
          </tr></thead>
          <tbody>
            {subs.map((s) => (
              <tr key={s.id}>
                <td>{s.name}{s.is_new && <span className="tag new">new</span>}</td>
                <td className="mono">{s.agent_id}</td>
                <td>
                  <div className="mono">{s.mu} ± {s.sigma}</div>
                  <div className="sigbar"><div style={{ width: `${Math.min(100, (s.sigma / 200) * 100)}%` }} /></div>
                </td>
                <td className="mono">{s.conservative}</td>
                <td className="mono">{s.wins}/{s.losses}/{s.draws}</td>
                <td className="mono">{s.games}</td>
                <td>
                  <span className={`badge ${s.status}`}>{s.status}</span>
                  {s.status === 'error' && (
                    <button className="btn ghost xs" onClick={() => setOpenLog(openLog === s.id ? null : s.id)}>logs</button>
                  )}
                </td>
                <td className="row" style={{ gap: 6, justifyContent: 'flex-end' }}>
                  <button className="btn ghost xs" disabled={s.status !== 'active'} onClick={() => doExport(s.id)}>export</button>
                  <button className="btn ghost xs danger" onClick={() => remove(s.id)}>✕</button>
                </td>
              </tr>
            ))}
            {subs.length === 0 && <tr><td colSpan="8" className="sub" style={{ padding: 18 }}>No submissions yet — create one above.</td></tr>}
          </tbody>
        </table>
      </div>

      {openLog && (
        <div className="panel pad" style={{ marginTop: 12 }}>
          <b style={{ fontFamily: 'var(--display)' }}>Validation error log</b>
          <pre className="report" style={{ marginTop: 8 }}>{subs.find((s) => s.id === openLog)?.error_log || '(no log)'}</pre>
        </div>
      )}
    </div>
  );
}
