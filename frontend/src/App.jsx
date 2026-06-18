import { useEffect, useState } from 'react';
import { api } from './api';
import { AuthProvider, useAuth } from './auth';
import BootGate from './components/BootGate';
import Login from './components/Login';
import WatchMode from './components/WatchMode';
import PlayMode from './components/PlayMode';
import TrainingDashboard from './components/TrainingDashboard';
import CardExplorer from './components/CardExplorer';
import DeckImport from './components/DeckImport';
import ModelArena from './components/ModelArena';
import RulesFeed from './components/RulesFeed';
import Competition from './components/Competition';
import Submissions from './components/Submissions';
import Scoreboard from './components/Scoreboard';
import Decks from './components/Decks';
import Multiplayer from './components/Multiplayer';
import Favorites from './components/Favorites';
import AdminPanel from './components/AdminPanel';
import { loadFavorites } from './favorites';

const NAV = [
  { id: 'watch', label: 'Watch AI vs AI', group: 'Arena' },
  { id: 'play', label: 'Play vs AI', group: 'Arena' },
  { id: 'multiplayer', label: '2-player', group: 'Arena' },
  { id: 'import', label: 'Deck import', group: 'Build' },
  { id: 'arena', label: 'Model arena', group: 'Intelligence' },
  { id: 'submissions', label: 'Ladder', group: 'Intelligence' },
  { id: 'scores', label: 'Model scores', group: 'Intelligence' },
  { id: 'train', label: 'Training lab', group: 'Intelligence' },
  { id: 'competition', label: 'Competition', group: 'Intelligence' },
  { id: 'favorites', label: 'Favorites', group: 'You' },
  { id: 'decks', label: 'Decks', group: 'Reference' },
  { id: 'cards', label: 'Card explorer', group: 'Reference' },
  { id: 'rules', label: 'Rules feed', group: 'Reference' },
];

function Shell() {
  const { user, ready, logout } = useAuth();
  const [tab, setTab] = useState('watch');
  const [decks, setDecks] = useState([]);
  const [models, setModels] = useState([]);
  const [launch, setLaunch] = useState(null);   // { mode, deck } from Favorites quick-launch

  const loadDecks = () => api.decks()
    .then((r) => setDecks(r.decks))
    .catch(() => setDecks(['charizard_ex', 'gardevoir_ex', 'miraidon_ex', 'roaring_moon_ex']));
  useEffect(() => { loadDecks(); }, []);
  useEffect(() => { api.agents().then((r) => setModels(r.models || [])).catch(() => setModels([])); }, []);
  useEffect(() => { if (user) loadFavorites(); }, [user]);

  function launchDeck(mode, deck) {
    setLaunch({ mode, deck, at: Date.now() });
    setTab(mode === 'watch' ? 'watch' : 'play');
  }

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
        {tab === 'watch' && <WatchMode decks={decks} agents={models} initialDeck={launch?.mode === 'watch' ? launch.deck : null} launchKey={launch?.at} />}
        {tab === 'play' && <PlayMode decks={decks} agents={models} initialDeck={launch?.mode === 'play' ? launch.deck : null} launchKey={launch?.at} />}
        {tab === 'multiplayer' && <Multiplayer />}
        {tab === 'import' && <DeckImport onImported={() => { loadDecks(); }} />}
        {tab === 'arena' && <ModelArena models={models} decks={decks} />}
        {tab === 'submissions' && <Submissions />}
        {tab === 'scores' && <Scoreboard />}
        {tab === 'train' && <TrainingDashboard />}
        {tab === 'competition' && <Competition />}
        {tab === 'favorites' && <Favorites onLaunch={launchDeck} />}
        {tab === 'decks' && <Decks />}
        {tab === 'cards' && <CardExplorer />}
        {tab === 'rules' && <RulesFeed />}
        {tab === 'admin' && user.is_admin && <AdminPanel />}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BootGate>
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </BootGate>
  );
}
