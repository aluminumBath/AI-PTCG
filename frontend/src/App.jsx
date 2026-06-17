import { useEffect, useState } from 'react';
import { api } from './api';
import { AuthProvider, useAuth } from './auth';
import Login from './components/Login';
import WatchMode from './components/WatchMode';
import PlayMode from './components/PlayMode';
import TrainingDashboard from './components/TrainingDashboard';
import CardExplorer from './components/CardExplorer';
import AdminPanel from './components/AdminPanel';

const NAV = [
  { id: 'watch', label: 'Watch AI vs AI', group: 'Arena' },
  { id: 'play', label: 'Play vs AI', group: 'Arena' },
  { id: 'train', label: 'Training lab', group: 'Intelligence' },
  { id: 'cards', label: 'Card explorer', group: 'Intelligence' },
];

function Shell() {
  const { user, ready, logout } = useAuth();
  const [tab, setTab] = useState('watch');
  const [decks, setDecks] = useState([]);

  useEffect(() => { api.decks().then((r) => setDecks(r.decks)).catch(() => setDecks(['charizard_ex', 'gardevoir_ex'])); }, []);

  if (!ready) return <div className="auth-wrap"><span className="spin" /></div>;
  if (!user) return <Login />;

  const groups = [...new Set(NAV.map((n) => n.group))];

  return (
    <div className="app">
      <aside className="rail">
        <div className="brand">
          <div className="mark" />
          <div><b>TCG Arena</b><span>AI Training Lab</span></div>
        </div>
        {groups.map((g) => (
          <div key={g}>
            <div className="nav-label">{g}</div>
            {NAV.filter((n) => n.group === g).map((n) => (
              <button key={n.id} className={`nav-item ${tab === n.id ? 'active' : ''}`} onClick={() => setTab(n.id)}>
                <span className="dot" />{n.label}
              </button>
            ))}
          </div>
        ))}
        {user.is_admin && (
          <div>
            <div className="nav-label">Admin</div>
            <button className={`nav-item ${tab === 'admin' ? 'active' : ''}`} onClick={() => setTab('admin')}>
              <span className="dot" />Control room
            </button>
          </div>
        )}
        <div className="spacer" />
        <div className="userbox">
          <div className="row between">
            <div className="who">
              <div className="avatar">{user.username[0]?.toUpperCase()}</div>
              <div>
                <div style={{ fontWeight: 600 }}>{user.username}</div>
                {user.is_admin && <div className="role">admin</div>}
              </div>
            </div>
            <button className="btn ghost sm" onClick={logout}>Sign out</button>
          </div>
        </div>
      </aside>

      <main className="main">
        {tab === 'watch' && <WatchMode decks={decks} />}
        {tab === 'play' && <PlayMode decks={decks} />}
        {tab === 'train' && <TrainingDashboard />}
        {tab === 'cards' && <CardExplorer />}
        {tab === 'admin' && user.is_admin && <AdminPanel />}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
