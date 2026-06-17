import { useState } from 'react';
import { useAuth } from '../auth';

export default function Login() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState('login');
  const [f, setF] = useState({ id: '', username: '', email: '', password: '' });
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit() {
    setErr(''); setBusy(true);
    try {
      if (mode === 'login') await login(f.id, f.password);
      else await register(f.username, f.email, f.password);
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="brand" style={{ justifyContent: 'center', paddingBottom: 26 }}>
          <div className="mark" />
          <div><b>TCG Arena</b><span>AI Training Lab</span></div>
        </div>
        <div className="panel">
          <h1>{mode === 'login' ? 'Sign in' : 'Create account'}</h1>
          <p className="sub" style={{ marginBottom: 18 }}>
            {mode === 'login' ? 'Access the arena, dashboards, and match history.' : 'Register to save matches and track results.'}
          </p>

          {mode === 'login' ? (
            <label className="field">Username or email
              <input value={f.id} onChange={(e) => setF({ ...f, id: e.target.value })} onKeyDown={(e) => e.key === 'Enter' && submit()} />
            </label>
          ) : (
            <>
              <label className="field">Username
                <input value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} />
              </label>
              <label className="field">Email
                <input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
              </label>
            </>
          )}
          <label className="field">Password
            <input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} onKeyDown={(e) => e.key === 'Enter' && submit()} />
          </label>

          {err && <div className="err">{err}</div>}
          <button className="btn primary" onClick={submit} disabled={busy}>
            {busy ? <span className="spin" /> : (mode === 'login' ? 'Sign in' : 'Create account')}
          </button>

          <div className="auth-switch">
            {mode === 'login' ? (
              <>New here? <button onClick={() => { setMode('register'); setErr(''); }}>Create an account</button></>
            ) : (
              <>Have an account? <button onClick={() => { setMode('login'); setErr(''); }}>Sign in</button></>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
