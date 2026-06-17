import { createContext, useContext, useEffect, useState } from 'react';
import { api } from './api';

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('tcg_token');
    if (!token) { setReady(true); return; }
    api.me()
      .then((r) => setUser(r.user))
      .catch(() => localStorage.removeItem('tcg_token'))
      .finally(() => setReady(true));
  }, []);

  const finish = (r) => {
    localStorage.setItem('tcg_token', r.token);
    setUser(r.user);
    return r.user;
  };

  const login = async (id, pw) => finish(await api.login(id, pw));
  const register = async (u, e, p) => finish(await api.register(u, e, p));
  const logout = () => { localStorage.removeItem('tcg_token'); setUser(null); };

  return (
    <AuthCtx.Provider value={{ user, ready, login, register, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}
