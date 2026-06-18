import { api } from '../api';

function dl(obj, name) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' }));
  const a = document.createElement('a'); a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

export default function ModelInfoModal({ model, onClose }) {
  if (!model) return null;

  async function exportModel() {
    try {
      const m = await api.modelExport(model.id);
      dl(m, `model-${model.id}.json`);
    } catch (e) { /* ignore */ }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <div className="row" style={{ gap: 8, alignItems: 'baseline' }}>
              <h2 style={{ margin: 0, fontFamily: 'var(--display)' }}>{model.label}</h2>
              <span className="tag">{model.family}</span>
              {model.speed && <span className="tag">{model.speed}</span>}
            </div>
            <div className="mono sub" style={{ fontSize: 12, marginTop: 4 }}>{model.id}</div>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn primary sm" onClick={exportModel}>Export model</button>
            <button className="btn ghost sm" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="modal-body">
          {model.summary && <p className="lead">{model.summary}</p>}

          <h4>Why this model</h4>
          <p>{model.why}</p>

          <h4>How it works</h4>
          <p>{model.how}</p>

          {model.params?.length > 0 && (
            <>
              <h4>Variables</h4>
              <table className="tbl compact">
                <thead><tr><th>Variable</th><th>Value</th><th>What it does</th></tr></thead>
                <tbody>
                  {model.params.map((p) => (
                    <tr key={p.name}>
                      <td className="mono">{p.name}</td>
                      <td className="mono">{p.value}</td>
                      <td>{p.why}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          <div className="row" style={{ gap: 18, marginTop: 14, flexWrap: 'wrap' }}>
            {model.strengths?.length > 0 && (
              <div style={{ flex: '1 1 220px' }}>
                <h4>Strengths</h4>
                <ul className="ticks">{model.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
              </div>
            )}
            {model.weaknesses?.length > 0 && (
              <div style={{ flex: '1 1 220px' }}>
                <h4>Trade-offs</h4>
                <ul className="ticks warn">{model.weaknesses.map((s, i) => <li key={i}>{s}</li>)}</ul>
              </div>
            )}
          </div>

          {model.imperfect_info && (
            <div className="ii-note">
              <b>Imperfect information:</b> {model.imperfect_info}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
