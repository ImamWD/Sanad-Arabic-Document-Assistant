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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Not JSON (e.g. an nginx error page): fall through to UNKNOWN_ERROR.
  }
  const error = isRecord(body) ? body.error : undefined;
  if (isRecord(error) && typeof error.code === 'string' && ERROR_CODE.test(error.code)) {
    return new ApiError(response.status, error.code, isRecord(error.params) ? error.params : {});
  }
  return new ApiError(response.status, UNKNOWN_ERROR);
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
  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
