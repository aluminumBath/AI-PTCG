import { useEffect, useRef, useState } from 'react';
import { api } from '../api';

const STATUS_COLOR = { ready: 'var(--ok)', pending: 'var(--warn)' };

// module-scoped so an in-flight (or finished) report survives leaving and
// re-entering the Competition tab — the job keeps running on the server.
const reportStore = { jobId: null, status: null, progress: 0, total: 0, markdown: null, best: null, filename: null };

export default function Competition() {
  const [info, setInfo] = useState(null);
  const [report, setReport] = useState(reportStore.markdown ? { ...reportStore } : null);
  const [run, setRun] = useState(reportStore.jobId ? { ...reportStore } : null);
  const [err, setErr] = useState('');
  const poll = useRef(null);

  // Kaggle export controls (deck + agent + optional writeup title/subtitle)
  const [decks, setDecks] = useState([]);
  const [agents, setAgents] = useState([]);
  const [xdeck, setXdeck] = useState('');
  const [xagent, setXagent] = useState('ismcts');
  const [xtitle, setXtitle] = useState('');
  const [xsub, setXsub] = useState('');

  useEffect(() => {
    api.decks().then((d) => {
      const ids = (d.decks || d || []).map((x) => (typeof x === 'string' ? x : x.id));
      setDecks(ids);
      if (ids.length) setXdeck((prev) => prev || ids[0]);
    }).catch(() => {});
    api.agents().then((a) => setAgents(a.models || a.agents || [])).catch(() => {});
  }, []);

  const dl = (url) => { const a = document.createElement('a'); a.href = url; a.rel = 'noopener'; a.click(); };

  useEffect(() => { api.competitionInfo().then(setInfo).catch((e) => setErr(e.message)); }, []);

  function startPolling() {
    clearInterval(poll.current);
    poll.current = setInterval(async () => {
      if (!reportStore.jobId) { clearInterval(poll.current); return; }
      try {
        const st = await api.competitionReportStatus(reportStore.jobId);
        Object.assign(reportStore, st);
        setRun({ ...reportStore });
        if (st.status !== 'running') {
          clearInterval(poll.current);
          if (st.status === 'done') setReport({ ...reportStore });
          if (st.status === 'error') setErr(st.error || 'report failed');
        }
      } catch (e) { /* keep polling; transient */ }
    }, 1500);
  }

  // re-attach to a still-running job when returning to the tab
  useEffect(() => {
    if (reportStore.jobId && reportStore.status === 'running') { setRun({ ...reportStore }); startPolling(); }
    return () => clearInterval(poll.current);
  }, []);

  async function generate() {
    setErr(''); setReport(null);
    Object.assign(reportStore, { jobId: null, status: 'running', progress: 0, total: 0, markdown: null, best: null });
    setRun({ ...reportStore });
    try {
      const r = await api.competitionReport({
        agents: ['heuristic', 'greedy', 'minimax', 'rl'],
        decks: ['charizard_ex', 'gardevoir_ex', 'miraidon_ex'],
        games_per_pairing: 3,
      });
      reportStore.jobId = r.job_id; reportStore.status = 'running';
      setRun({ ...reportStore });
      startPolling();
    } catch (e) { setErr(e.message); reportStore.status = 'error'; }
  }

  const busy = run?.status === 'running';

  function download() {
    if (!report?.markdown) return;
    const blob = new Blob([report.markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = report.filename || 'STRATEGY_REPORT.md';
    a.click(); URL.revokeObjectURL(url);
  }

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Competition</div>
        <h1>PTCG AI Battle Challenge</h1>
        <p className="sub">This project targets The Pokémon Company's Kaggle challenge. The Simulation Category runs your agent in continuous matches; the prize-bearing Strategy Category judges the reasoning behind it. Generate a strategy writeup from live tournament data below.</p>
      </div>

      {err && <div className="err">{err}</div>}
      {!info ? (
        <div className="panel pad"><span className="live"><span className="spin" /> loading…</span></div>
      ) : (
        <>
          <div className="row" style={{ gap: 16, alignItems: 'stretch', marginBottom: 16 }}>
            {info.categories.map((c) => (
              <div className="panel pad grow" key={c.key} style={{ minWidth: 280 }}>
                <div className="row between">
                  <b style={{ fontFamily: 'var(--display)' }}>{c.label}</b>
                  {c.key === 'strategy' && <span className="pill">prizes</span>}
                </div>
                <p className="sub" style={{ marginTop: 8, fontSize: 13 }}>{c.summary}</p>
                <a className="btn ghost sm" href={c.url} target="_blank" rel="noreferrer" style={{ marginTop: 10 }}>Open on Kaggle ↗</a>
              </div>
            ))}
          </div>

          <div className="panel pad" style={{ marginBottom: 16 }}>
            <b style={{ fontFamily: 'var(--display)' }}>Readiness</b>
            <div style={{ marginTop: 10 }}>
              {info.readiness.map((r) => (
                <div className="rule" key={r.item}>
                  <div className="rule-name">
                    <span style={{ color: STATUS_COLOR[r.status] || 'var(--muted)' }}>
                      {r.status === 'ready' ? '✓' : '◐'}
                    </span>
                    {r.item}
                    <span className="tag" style={{ marginLeft: 8 }}>{r.status}</span>
                  </div>
                  <div className="rule-detail">{r.detail}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel pad">
            <div className="row between">
              <b style={{ fontFamily: 'var(--display)' }}>Strategy report</b>
              <div className="row">
                <button className="btn primary sm" onClick={generate} disabled={busy}>
                  {busy ? <span className="spin" /> : 'Generate from live tournament'}
                </button>
                {report?.markdown && <button className="btn sm" onClick={download}>Download .md</button>}
              </div>
            </div>
            {busy && (
              <div style={{ marginTop: 10 }}>
                <div className="bar"><div className="bar-fill" style={{ width: `${run?.total ? (100 * run.progress) / run.total : 12}%` }} /></div>
                <p className="sub" style={{ fontSize: 12, marginTop: 6 }}>
                  Running matches and writing the report… {run?.total ? `${run.progress}/${run.total} games` : ''} — you can switch tabs; it keeps running.
                </p>
              </div>
            )}
            {report?.markdown && (
              <pre className="report" style={{ marginTop: 12 }}>{report.markdown}</pre>
            )}
          </div>

          <div className="panel pad" style={{ marginTop: 16 }}>
            <div className="row between" style={{ marginBottom: 4 }}>
              <b style={{ fontFamily: 'var(--display)' }}>Export for Kaggle</b>
              <span className="tag">Simulation + Strategy</span>
            </div>
            <p className="sub" style={{ fontSize: 12.5, marginTop: 0 }}>
              Pick a deck and the agent that pilots it, then export a ready-to-submit
              Simulation bundle or a Strategy Writeup draft.
            </p>
            <div className="row" style={{ gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
              <label className="field">Deck
                <select value={xdeck} onChange={(e) => setXdeck(e.target.value)} style={{ minWidth: 180 }}>
                  {decks.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>
              <label className="field">Agent
                <select value={xagent} onChange={(e) => setXagent(e.target.value)} style={{ minWidth: 160 }}>
                  {(agents.length ? agents : [{ id: 'ismcts', label: 'ISMCTS' }]).map((m) => {
                    const id = typeof m === 'string' ? m : m.id;
                    const label = typeof m === 'string' ? m : (m.label || m.id);
                    return <option key={id} value={id}>{label}</option>;
                  })}
                </select>
              </label>
            </div>

            <div className="row" style={{ gap: 10, marginTop: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <button className="btn primary" disabled={!xdeck} onClick={() => dl(api.exportSimUrl(xdeck, xagent))}>
                Export AI sim (.tar.gz)
              </button>
              <span className="sub" style={{ fontSize: 12, maxWidth: 360 }}>
                Top-level <code>main.py</code> + <code>deck.csv</code>. Add the <code>cg/</code> library,
                then <code>tar -czvf submission.tar.gz *</code>.
              </span>
            </div>

            <div style={{ borderTop: '1px solid var(--line)', margin: '14px 0' }} />

            <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
              <label className="field grow">Writeup title (optional)
                <input value={xtitle} onChange={(e) => setXtitle(e.target.value)} placeholder="e.g. Gardevoir ex — patient control" />
              </label>
              <label className="field grow">Subtitle (optional)
                <input value={xsub} onChange={(e) => setXsub(e.target.value)} placeholder="one-line thesis" />
              </label>
            </div>
            <div className="row" style={{ gap: 10, marginTop: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <button className="btn" disabled={!xdeck} onClick={() => dl(api.exportStrategyUrl(xdeck, xagent, xtitle, xsub))}>
                Export AI strategy (Writeup)
              </button>
              <span className="sub" style={{ fontSize: 12, maxWidth: 360 }}>
                Markdown Writeup (≤2000 words) structured for the Model 70% / Deck 20% / Report 10% rubric.
                Add license-compliant figures to the Media Gallery before submitting.
              </span>
            </div>
          </div>

          <p className="sub" style={{ marginTop: 14, fontSize: 12 }}>{info.disclaimer}</p>
        </>
      )}
    </div>
  );
}
