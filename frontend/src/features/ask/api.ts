import { queryOptions } from '@tanstack/react-query';

import {
  ApiError,
  apiFetch,
  errorFromResponse,
  isRecord,
  NETWORK_ERROR,
  parseJson,
  UNKNOWN_ERROR,
} from '../../lib/api';
import { createSseParser, type SseMessage } from './sse';
import type {
  AnswerResult,
  Band,
  Citation,
  NearestDocument,
  QuerySummary,
  RefusalReason,
  StoredQuery,
  StreamEvent,
} from './types';

const OUTCOMES = ['answered', 'low_confidence', 'no_answer'] as const;
const BANDS = ['answer', 'low_confidence', 'refuse'] as const;
const REASONS = ['gate', 'sentinel', 'no_valid_citation'] as const;

function oneOf<T extends string>(value: unknown, options: readonly T[]): T | null {
  return options.includes(value as T) ? (value as T) : null;
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

const text = (value: unknown) => (typeof value === 'string' ? value : '');

function decodeCitation(raw: unknown): Citation | null {
  if (!isRecord(raw)) return null;
  const { rank, document_id, title, page_number } = raw;
  if (!isCount(rank) || typeof document_id !== 'string' || !document_id) return null;
  if (!isCount(page_number) || page_number < 1) return null;
  return {
    rank,
    document_id,
    title: text(title),
    page_number,
    snippet: text(raw.snippet),
    file_type: text(raw.file_type),
    is_converted: raw.is_converted === true,
  };
}

function decodeNearest(raw: unknown): NearestDocument | null {
  if (!isRecord(raw) || typeof raw.document_id !== 'string' || !raw.document_id) return null;
  return { document_id: raw.document_id, title: text(raw.title) };
}

function decodeList<T>(raw: unknown, decode: (item: unknown) => T | null): T[] {
  return Array.isArray(raw) ? raw.map(decode).filter((item): item is T => item !== null) : [];
}

/**
 * A validated answer from `final` or the history. It fails closed (D4): an unknown outcome
 * is malformed (null), and an answer without text or without a valid citation becomes a
 * refusal, because no valid citation means no answer. The server enforces the same rule; the
 * screen never relies on that alone.
 */
export function decodeAnswer(raw: unknown, queryId?: string): AnswerResult | null {
  if (!isRecord(raw)) return null;
  const outcome = oneOf(raw.outcome, OUTCOMES);
  if (!outcome) return null;
  const answer = typeof raw.answer === 'string' && raw.answer.trim() ? raw.answer : null;
  const citations = decodeList(raw.citations, decodeCitation);
  const base = {
    query_id: queryId ?? text(raw.query_id),
    band: oneOf<Band>(raw.band, BANDS),
    nearest_documents: decodeList(raw.nearest_documents, decodeNearest),
  };
  if (outcome === 'no_answer' || answer === null || citations.length === 0) {
    const reason: RefusalReason | null =
      outcome === 'no_answer' ? oneOf(raw.refusal_reason, REASONS) : 'no_valid_citation';
    return { ...base, outcome: 'no_answer', refusal_reason: reason, answer: null, citations: [] };
  }
  return { ...base, outcome, refusal_reason: null, answer, citations };
}

/**
 * One SSE message as a stream event (SYSTEM_DESIGN §6). Unknown events and malformed progress
 * events are skipped (null). A malformed `final` and every `error` event are thrown, so the
 * caller stops and nothing unvalidated stays on screen.
 */
export function decodeEvent({ event, data }: SseMessage, status = 200): StreamEvent | null {
  if (event === 'error') throw errorFromResponse(status, data);
  const payload = parseJson(data);
  if (event === 'final') {
    const result = decodeAnswer(payload);
    if (!result) throw new ApiError(status, UNKNOWN_ERROR);
    return { type: 'final', result };
  }
  if (!isRecord(payload)) return null;
  if (event === 'token') {
    return typeof payload.text === 'string' ? { type: 'token', text: payload.text } : null;
  }
  if (event === 'eta') {
    const seconds = payload.expected_seconds;
    return typeof seconds === 'number' && Number.isFinite(seconds) && seconds > 0
      ? { type: 'eta', expectedSeconds: seconds, capped: payload.capped === true }
      : null;
  }
  if (event !== 'stage') return null;
  switch (payload.stage) {
    case 'queued':
      return isCount(payload.position)
        ? { type: 'stage', stage: 'queued', position: payload.position }
        : null;
    case 'reading':
      return isCount(payload.sources)
        ? {
            type: 'stage',
            stage: 'reading',
            sources: payload.sources,
            band: oneOf(payload.band, BANDS),
          }
        : null;
    case 'searching':
    case 'writing':
      return { type: 'stage', stage: payload.stage };
    default:
      return null;
  }
}

/**
 * POST /api/ask/stream and hand each event to `onEvent` until `final`. Same-origin with the
 * CSRF header, like apiFetch. Failures throw ApiError: the response's error envelope, an
 * `error` event, NETWORK_ERROR when the connection drops or the stream ends without `final`.
 * An abort rethrows the AbortError.
 */
export async function streamAsk(
  question: string,
  onEvent: (event: StreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch('/api/ask/stream', {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        'X-Sanad': '1',
      },
      credentials: 'same-origin',
      body: JSON.stringify({ question }),
      signal,
    });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new ApiError(0, NETWORK_ERROR);
  }
  // Not JSON (an nginx error page), or unreadable: UNKNOWN_ERROR.
  if (!response.ok) throw errorFromResponse(response.status, await response.text().catch(() => ''));
  if (!response.body) throw new ApiError(response.status, UNKNOWN_ERROR);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const messages: SseMessage[] = [];
  const parser = createSseParser((message) => messages.push(message));
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
      for (const message of messages.splice(0)) {
        const event = decodeEvent(message, response.status);
        if (!event) continue;
        onEvent(event);
        if (event.type === 'final') return;
      }
    }
  } catch (error) {
    if (signal.aborted || error instanceof ApiError) throw error;
    throw new ApiError(0, NETWORK_ERROR);
  } finally {
    reader.cancel().catch(() => undefined);
  }
  // The stream ended without `final`: whatever streamed was never validated.
  throw new ApiError(0, NETWORK_ERROR);
}

function decodeSummary(raw: unknown): QuerySummary | null {
  if (!isRecord(raw)) return null;
  const outcome = oneOf(raw.outcome, OUTCOMES);
  const { id, question, created_at } = raw;
  if (typeof id !== 'string' || !id || typeof question !== 'string' || !outcome) return null;
  return { id, question, outcome, created_at: text(created_at) };
}

export const queriesKey = ['queries'] as const;

/**
 * The history panel: GET /api/queries, the user's own questions, newest first. `scope` is the
 * session the cache belongs to (useHistoryScope).
 */
export function queriesQuery(scope: number) {
  return queryOptions({
    queryKey: [...queriesKey, scope],
    queryFn: async ({ signal }) =>
      decodeList(await apiFetch<unknown>('/queries', { signal }), decodeSummary),
  });
}

/** One stored question and its answer. Stored answers never change, so it never refetches. */
export function storedQueryQuery(scope: number, id: string) {
  return queryOptions({
    queryKey: [...queriesKey, scope, id],
    queryFn: async ({ signal }): Promise<StoredQuery> => {
      const raw = await apiFetch<unknown>(`/queries/${encodeURIComponent(id)}`, { signal });
      const result = decodeAnswer(raw, id);
      if (!isRecord(raw) || !result || typeof raw.question !== 'string') {
        throw new ApiError(200, UNKNOWN_ERROR);
      }
      return { question: raw.question, created_at: text(raw.created_at), result };
    },
    staleTime: Infinity,
  });
}
