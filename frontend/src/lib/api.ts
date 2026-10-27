// The one HTTP client for /api (SYSTEM_DESIGN §7, §9). Same-origin only, cookie session.
// Failures become ApiError with the server's error code; the UI translates the code and never
// shows server prose.

export const NETWORK_ERROR = 'NETWORK_ERROR';
export const UNKNOWN_ERROR = 'UNKNOWN_ERROR';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly params: Readonly<Record<string, unknown>>;

  /** `status` is 0 when the server could not be reached. */
  constructor(status: number, code: string, params: Record<string, unknown> = {}) {
    super(code);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.params = params;
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  /** JSON-serialisable value, or FormData for multipart uploads. */
  body?: unknown;
  signal?: AbortSignal;
}

const ERROR_CODE = /^[A-Z][A-Z0-9_]*$/;

/** A JSON object (not null, not an array), the shape of every body the API sends. */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** `text` parsed as JSON, or undefined when it isn't JSON (an nginx error page, say). */
export function parseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return undefined;
  }
}

/**
 * The ApiError for a failed request, from its status and body text: the server's
 * `{"error": {"code", "params"}}`, or UNKNOWN_ERROR for anything else. The one place an
 * error body becomes an ApiError (fetch, XHR and the SSE `error` event all come here).
 */
export function errorFromResponse(status: number, text: string): ApiError {
  const body = parseJson(text);
  const error = isRecord(body) ? body.error : undefined;
  if (isRecord(error) && typeof error.code === 'string' && ERROR_CODE.test(error.code)) {
    return new ApiError(status, error.code, isRecord(error.params) ? error.params : {});
  }
  return new ApiError(status, UNKNOWN_ERROR);
}

/**
 * Call `/api{path}`. State-changing requests carry `X-Sanad` and a JSON (or multipart) body,
 * which the server's CSRF check requires (SYSTEM_DESIGN §9).
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options;
  const headers = new Headers({ Accept: 'application/json' });
  const init: RequestInit = { method, headers, credentials: 'same-origin' };
  if (signal) init.signal = signal;
  if (method !== 'GET') {
    headers.set('X-Sanad', '1');
    if (body instanceof FormData) {
      init.body = body;
    } else {
      headers.set('Content-Type', 'application/json');
      init.body = JSON.stringify(body ?? {});
    }
  }

  let response: Response;
  try {
    response = await fetch(`/api${path}`, init);
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(0, NETWORK_ERROR);
  }
  // A body that can't be read counts as no body: UNKNOWN_ERROR.
  if (!response.ok) throw errorFromResponse(response.status, await response.text().catch(() => ''));
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
