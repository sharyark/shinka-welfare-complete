/**
 * The app's single API client, plus one function per endpoint the app uses.
 * Tokens live in memory here and are saved to secure storage by AuthContext.
 */
import { createClient } from './client';
import type {
  Application,
  DeliverBody,
  Lookup,
  Me,
  MyHousehold,
  Page,
  Program,
  QRCard,
  Summary,
  Tokens,
} from './types';

export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

let tokens: Tokens | null = null;
let onTokensChanged: (tokens: Tokens | null) => void = () => {};

export function setSession(next: Tokens | null) {
  tokens = next;
}

export function listenForSession(listener: (tokens: Tokens | null) => void) {
  onTokensChanged = listener;
}

const client = createClient({
  baseUrl: API_URL,
  fetch: (...args) => fetch(...args),
  getTokens: () => tokens,
  setTokens: (next) => {
    tokens = next;
    onTokensChanged(next);
  },
});

const post = <T>(path: string, body?: unknown, auth = true) => client.request<T>(path, { method: 'POST', body, auth });

export const api = {
  // Login (no token needed)
  requestCode: (phone: string) => post<{ detail: string }>('/auth/otp/request/', { phone }, false),
  verifyCode: (phone: string, code: string) =>
    post<{ pin_token: string }>('/auth/otp/verify/', { phone, code }, false),
  setPin: (pin_token: string, pin: string) => post<{ detail: string }>('/auth/pin/set/', { pin_token, pin }, false),
  pinLogin: (body: { phone: string; pin: string; device_id: string; platform: string; device_name: string }) =>
    post<Tokens>('/auth/pin/login/', body, false),
  logout: (refresh: string) => post<void>('/auth/logout/', { refresh }, false),

  me: () => client.request<Me>('/me/'),

  // Family
  myHousehold: () => client.request<MyHousehold>('/me/household/'),
  mySummary: (year?: number) => client.request<Summary>(`/me/summary/${year ? `?year=${year}` : ''}`),
  myQR: () => client.request<QRCard>('/me/qr/'),
  programs: () => client.request<Program[]>('/benefits/programs/'),
  applications: () => client.request<Page<Application>>('/applications/'),
  apply: (body: { household: string; program: string; description: string; amount_requested?: string; needed_by?: string }) =>
    post<Application>('/applications/', body),
  withdraw: (id: string) => post<Application>(`/applications/${id}/withdraw/`),

  // Volunteer
  lookup: (q: string) => client.request<Lookup>(`/distribution/lookup/?q=${encodeURIComponent(q)}`),
  deliver: (body: DeliverBody) => post<{ id: string }>('/distribution/deliver/', body),
};
