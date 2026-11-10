import { ApiError, createClient } from '../src/api/client';
import type { Tokens } from '../src/api/types';

function json(status: number, body: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}

function setup(responses: Response[], start: Tokens | null = { access: 'old', refresh: 'r1' }) {
  let tokens = start;
  const calls: { url: string; init: RequestInit }[] = [];
  const fetchMock = jest.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    const next = responses.shift();
    if (!next) throw new TypeError('Network request failed');
    return next;
  });
  const client = createClient({
    baseUrl: 'http://api.test/',
    fetch: fetchMock as unknown as typeof fetch,
    getTokens: () => tokens,
    setTokens: (t) => {
      tokens = t;
    },
  });
  return { client, calls, tokens: () => tokens };
}

test('sends the access token and parses JSON', async () => {
  const { client, calls } = setup([json(200, { name: 'Ali' })]);
  await expect(client.request('/me/')).resolves.toEqual({ name: 'Ali' });
  expect(calls[0].url).toBe('http://api.test/api/v1/me/');
  expect((calls[0].init.headers as Record<string, string>).Authorization).toBe('Bearer old');
});

test('refreshes an expired token once and repeats the request', async () => {
  const { client, calls, tokens } = setup([
    json(401, { detail: 'expired' }),
    json(200, { access: 'new', refresh: 'r2' }),
    json(200, { ok: true }),
  ]);
  await expect(client.request('/me/')).resolves.toEqual({ ok: true });
  expect(tokens()).toEqual({ access: 'new', refresh: 'r2' });
  expect((calls[2].init.headers as Record<string, string>).Authorization).toBe('Bearer new');
});

test('logs out when the refresh token is refused (e.g. phone blocked)', async () => {
  const { client, tokens } = setup([json(401, {}), json(401, { detail: 'blocked' }), json(401, {})]);
  await expect(client.request('/me/')).rejects.toBeInstanceOf(ApiError);
  expect(tokens()).toBeNull();
});

test('business rule errors keep the backend code', async () => {
  const { client } = setup([json(409, { detail: 'Already collected.', code: 'already_delivered' })]);
  await expect(client.request('/distribution/deliver/', { method: 'POST', body: {} })).rejects.toMatchObject({
    status: 409,
    code: 'already_delivered',
    message: 'Already collected.',
  });
});

test('field errors become a readable message', async () => {
  const { client } = setup([json(400, { phone: ["'x' is not a valid Pakistani mobile number."] })]);
  await expect(client.request('/auth/otp/request/', { method: 'POST', body: {}, auth: false })).rejects.toMatchObject({
    code: 'http_400',
    message: "'x' is not a valid Pakistani mobile number.",
  });
});

test('no connection becomes a network error', async () => {
  const { client } = setup([]);
  const error = await client.request('/me/').catch((e) => e);
  expect(error).toBeInstanceOf(ApiError);
  expect(error.isNetwork).toBe(true);
});

test('public endpoints send no token', async () => {
  const { client, calls } = setup([json(200, {})]);
  await client.request('/auth/otp/request/', { method: 'POST', body: { phone: '0300' }, auth: false });
  expect((calls[0].init.headers as Record<string, string>).Authorization).toBeUndefined();
});
