import { describe, expect, it, vi } from 'vitest';

import { ApiError, apiFetch, NETWORK_ERROR, UNKNOWN_ERROR } from './api';
import { errorCodeOf } from './errors';

function respond(status: number, body?: unknown, contentType = 'application/json') {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': contentType },
    }),
  );
}

function sent(fetchSpy: ReturnType<typeof respond>) {
  const [url, init] = fetchSpy.mock.calls[0] ?? [];
  return { url, init: init ?? {}, headers: new Headers(init?.headers) };
}

async function rejection(promise: Promise<unknown>): Promise<ApiError> {
  const error: unknown = await promise.then(
    () => null,
    (e: unknown) => e,
  );
  if (!(error instanceof ApiError)) throw new Error('expected an ApiError');
  return error;
}

describe('apiFetch', () => {
  it('GETs same-origin /api paths with the session cookie and no CSRF header', async () => {
    const fetchSpy = respond(200, { status: 'ok' });
    await expect(apiFetch('/health')).resolves.toEqual({ status: 'ok' });
    const { url, init, headers } = sent(fetchSpy);
    expect(url).toBe('/api/health');
    expect(init.method).toBe('GET');
    expect(init.credentials).toBe('same-origin');
    expect(init.body).toBeUndefined();
    expect(headers.get('X-Sanad')).toBeNull();
  });

  it('sends JSON with the X-Sanad header on state-changing requests', async () => {
    const fetchSpy = respond(200, { id: 'u1' });
    await apiFetch('/auth/login', { method: 'POST', body: { email: 'a@example.org' } });
    const { init, headers } = sent(fetchSpy);
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"email":"a@example.org"}');
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(headers.get('X-Sanad')).toBe('1');
  });

  it('sends an empty JSON object when a POST has no body', async () => {
    const fetchSpy = respond(204);
    await expect(apiFetch('/auth/logout', { method: 'POST' })).resolves.toBeUndefined();
    expect(sent(fetchSpy).init.body).toBe('{}');
  });

  it('passes FormData through for uploads, letting the browser set the boundary', async () => {
    const fetchSpy = respond(201, { id: 'd1' });
    const form = new FormData();
    form.append('title', 'التقرير السنوي');
    await apiFetch('/documents', { method: 'POST', body: form });
    const { init, headers } = sent(fetchSpy);
    expect(init.body).toBe(form);
    expect(headers.get('Content-Type')).toBeNull();
    expect(headers.get('X-Sanad')).toBe('1');
  });

  it('turns {"error": {code, params}} into an ApiError', async () => {
    respond(429, { error: { code: 'RATE_LIMITED', params: { retry_after: 30 } } });
    const error = await rejection(apiFetch('/auth/login', { method: 'POST', body: {} }));
    expect(error).toMatchObject({ status: 429, code: 'RATE_LIMITED', params: { retry_after: 30 } });
  });

  it('never surfaces server prose: anything but an error code becomes UNKNOWN_ERROR', async () => {
    respond(500, { detail: 'Traceback (most recent call last): …' });
    const error = await rejection(apiFetch('/me'));
    expect(error).toMatchObject({ status: 500, code: UNKNOWN_ERROR, params: {} });
    expect(error.message).toBe(UNKNOWN_ERROR);

    respond(502, '<html>Bad Gateway</html>', 'text/html');
    expect((await rejection(apiFetch('/me'))).code).toBe(UNKNOWN_ERROR);

    respond(400, { error: { code: 'Something broke', params: {} } });
    expect((await rejection(apiFetch('/me'))).code).toBe(UNKNOWN_ERROR);
  });

  it('reports an unreachable server as NETWORK_ERROR (status 0)', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
    expect(await rejection(apiFetch('/me'))).toMatchObject({ status: 0, code: NETWORK_ERROR });
  });
});

describe('errorCodeOf', () => {
  it('keeps translated codes and maps everything else to UNKNOWN_ERROR', () => {
    expect(errorCodeOf(new ApiError(401, 'INVALID_CREDENTIALS'))).toBe('INVALID_CREDENTIALS');
    expect(errorCodeOf(new ApiError(400, 'SOME_FUTURE_CODE'))).toBe('UNKNOWN_ERROR');
    expect(errorCodeOf(new Error('boom'))).toBe('UNKNOWN_ERROR');
  });
});
