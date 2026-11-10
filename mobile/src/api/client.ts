/**
 * A tiny HTTP client for the Shinka API.
 *
 * - Adds the access token to every request.
 * - When the access token has expired (401), uses the refresh token once to get
 *   a new one and repeats the request. If that fails too, the user is logged out.
 * - Turns every failure into an ApiError with the backend's `code`
 *   (e.g. "already_delivered"), or code "network" when there is no connection.
 *
 * It is created with its dependencies passed in, so tests can use a fake fetch.
 */
import type { Tokens } from './types';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields: Record<string, unknown> = {},
  ) {
    super(message);
  }

  get isNetwork() {
    return this.status === 0;
  }
}

type Deps = {
  baseUrl: string;
  fetch: typeof fetch;
  getTokens: () => Tokens | null;
  setTokens: (tokens: Tokens | null) => void | Promise<void>;
};

type Options = { method?: string; body?: unknown; auth?: boolean };

function firstMessage(data: unknown): string {
  if (data && typeof data === 'object') {
    const detail = (data as Record<string, unknown>).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && typeof detail[0] === 'string') return detail[0];
    for (const value of Object.values(data as Record<string, unknown>)) {
      if (typeof value === 'string') return value;
      if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
    }
  }
  return 'Something went wrong. Please try again.';
}

export function createClient(deps: Deps) {
  const root = `${deps.baseUrl.replace(/\/$/, '')}/api/v1`;

  async function send(path: string, { method = 'GET', body, auth = true }: Options, token?: string) {
    const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json';
    if (auth && token) headers.Authorization = `Bearer ${token}`;
    try {
      return await deps.fetch(`${root}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, 'network', 'No internet connection.');
    }
  }

  async function refresh(): Promise<string | null> {
    const tokens = deps.getTokens();
    if (!tokens) return null;
    const response = await send('/auth/token/refresh/', { method: 'POST', body: { refresh: tokens.refresh }, auth: false });
    if (!response.ok) {
      await deps.setTokens(null); // refresh token expired or phone blocked: log out
      return null;
    }
    const data = (await response.json()) as Partial<Tokens>;
    const next = { access: data.access!, refresh: data.refresh ?? tokens.refresh }; // refresh tokens rotate
    await deps.setTokens(next);
    return next.access;
  }

  async function request<T>(path: string, options: Options = {}): Promise<T> {
    const auth = options.auth ?? true;
    let response = await send(path, options, deps.getTokens()?.access);
    if (response.status === 401 && auth && deps.getTokens()) {
      const access = await refresh();
      if (access) response = await send(path, options, access);
    }
    if (response.status === 204) return undefined as T;
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const code = typeof data?.code === 'string' ? data.code : `http_${response.status}`;
      throw new ApiError(response.status, code, firstMessage(data), data);
    }
    return data as T;
  }

  return { request };
}

export type Client = ReturnType<typeof createClient>;
