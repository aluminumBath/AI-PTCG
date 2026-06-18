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

          <p className="sub" style={{ marginTop: 14, fontSize: 12 }}>{info.disclaimer}</p>
        </>
      )}
    </div>
  );
}
