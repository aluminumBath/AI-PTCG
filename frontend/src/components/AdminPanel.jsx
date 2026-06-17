import { useEffect, useState } from 'react';
import { api } from '../api';

export default function AdminPanel() {
  const [users, setUsers] = useState([]);
  const [games, setGames] = useState([]);
  const [err, setErr] = useState('');

  useEffect(() => {
    api.adminUsers().then((r) => setUsers(r.users)).catch((e) => setErr(e.message));
    api.myGames().then((r) => setGames(r.games)).catch(() => {});
  }, []);

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Admin</div>
        <h1>Control room</h1>
        <p className="sub">Registered accounts and recent saved matches. Visible to admin users only.</p>
      </div>

      {err && <div className="err">{err}</div>}

      <div className="panel pad" style={{ marginBottom: 16 }}>
        <b style={{ fontFamily: 'var(--display)' }}>Users</b>
        <table className="tbl" style={{ marginTop: 10 }}>
          <thead><tr><th>ID</th><th>Username</th><th>Email</th><th>Role</th><th>Joined</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td style={{ fontFamily: 'var(--mono)' }}>{u.id}</td>
                <td>{u.username}</td>
                <td style={{ color: 'var(--muted)' }}>{u.email}</td>
                <td>{u.is_admin ? <span className="pill">admin</span> : <span className="tag">member</span>}</td>
                <td style={{ color: 'var(--muted)', fontFamily: 'var(--mono)', fontSize: 12 }}>{new Date(u.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel pad">
        <b style={{ fontFamily: 'var(--display)' }}>Your saved matches</b>
        {games.length === 0 ? (
          <p className="sub" style={{ marginTop: 8 }}>No saved games yet — save one from Watch mode.</p>
        ) : (
          <table className="tbl" style={{ marginTop: 10 }}>
            <thead><tr><th>ID</th><th>Mode</th><th>Matchup</th><th>Winner</th><th>Turns</th></tr></thead>
            <tbody>
              {games.map((g) => (
                <tr key={g.id}>
                  <td style={{ fontFamily: 'var(--mono)' }}>{g.id}</td>
                  <td>{g.mode}</td>
                  <td>{g.deck_a} vs {g.deck_b}</td>
                  <td>{g.winner || '—'}</td>
                  <td style={{ fontFamily: 'var(--mono)' }}>{g.turns}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
