/**
 * Who is logged in. Tokens are kept in secure storage, so the app stays logged
 * in after a restart. If the refresh token stops working (expired, or the phone
 * was blocked by the office), the app goes back to the login screen.
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { Platform } from 'react-native';

import { api, listenForSession, setSession } from '../api';
import type { Me, Tokens } from '../api/types';
import { getDeviceId, storage } from './storage';

const TOKENS_KEY = 'shinka.tokens';
const PHONE_KEY = 'shinka.phone';

type State = { status: 'loading' } | { status: 'loggedOut' } | { status: 'loggedIn'; me: Me };

type Ctx = {
  state: State;
  savedPhone: string | null;
  rememberPhone: (phone: string) => Promise<void>;
  loginWithPin: (phone: string, pin: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: 'loading' });
  const [savedPhone, setSavedPhone] = useState<string | null>(null);

  const saveTokens = useCallback(async (tokens: Tokens | null) => {
    setSession(tokens);
    if (tokens) await storage.setItem(TOKENS_KEY, JSON.stringify(tokens));
    else {
      await storage.removeItem(TOKENS_KEY);
      setState({ status: 'loggedOut' });
    }
  }, []);

  useEffect(() => {
    listenForSession((tokens) => {
      if (tokens) storage.setItem(TOKENS_KEY, JSON.stringify(tokens));
      else saveTokens(null);
    });
    (async () => {
      setSavedPhone(await storage.getItem(PHONE_KEY));
      const raw = await storage.getItem(TOKENS_KEY);
      if (!raw) return setState({ status: 'loggedOut' });
      setSession(JSON.parse(raw) as Tokens);
      try {
        setState({ status: 'loggedIn', me: await api.me() });
      } catch {
        await saveTokens(null);
      }
    })();
  }, [saveTokens]);

  const rememberPhone = useCallback(async (phone: string) => {
    setSavedPhone(phone);
    await storage.setItem(PHONE_KEY, phone);
  }, []);

  const loginWithPin = useCallback(
    async (phone: string, pin: string) => {
      const tokens = await api.pinLogin({
        phone,
        pin,
        device_id: await getDeviceId(),
        platform: Platform.OS === 'ios' || Platform.OS === 'android' ? Platform.OS : 'web',
        device_name: `${Platform.OS} phone`,
      });
      await saveTokens(tokens);
      await rememberPhone(phone);
      setState({ status: 'loggedIn', me: await api.me() });
    },
    [rememberPhone, saveTokens],
  );

  const logout = useCallback(async () => {
    const raw = await storage.getItem(TOKENS_KEY);
    if (raw) api.logout((JSON.parse(raw) as Tokens).refresh).catch(() => {}); // best effort
    await saveTokens(null);
  }, [saveTokens]);

  return (
    <AuthContext.Provider value={{ state, savedPhone, rememberPhone, loginWithPin, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

/** Which home screen fits the user's roles. */
export function homeFor(me: Me): '/family' | '/volunteer' | '/office' {
  if (me.roles.includes('Beneficiary')) return '/family';
  if (me.roles.some((r) => ['Volunteer', 'Program Coordinator', 'President'].includes(r))) return '/volunteer';
  return '/office';
}
