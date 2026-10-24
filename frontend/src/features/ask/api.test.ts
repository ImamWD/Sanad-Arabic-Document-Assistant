import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../lib/api';
import { decodeAnswer, decodeEvent, streamAsk } from './api';
import {
  FINAL_ANSWERED,
  FINAL_GATE,
  FINAL_SENTINEL,
  fakeStream,
  PDF_CITATION,
  sse,
} from './test-fixtures';
import type { StreamEvent } from './types';

afterEach(() => {
  vi.restoreAllMocks();
});

const message = (event: string, data: unknown) => ({ event, data: JSON.stringify(data) });

describe('decodeEvent', () => {
  it('reads every stage, the estimate and tokens', () => {
    expect(decodeEvent(message('stage', { stage: 'queued', position: 2 }))).toEqual({
      type: 'stage',
      stage: 'queued',
      position: 2,
    });
    expect(decodeEvent(message('stage', { stage: 'searching' }))).toEqual({
      type: 'stage',
      stage: 'searching',
    });
    expect(
      decodeEvent(message('stage', { stage: 'reading', sources: 6, band: 'low_confidence' })),
    ).toEqual({ type: 'stage', stage: 'reading', sources: 6, band: 'low_confidence' });
    expect(decodeEvent(message('stage', { stage: 'writing' }))).toEqual({
      type: 'stage',
      stage: 'writing',
    });
    expect(decodeEvent(message('eta', { expected_seconds: 45 }))).toEqual({
      type: 'eta',
      expectedSeconds: 45,
    });
    expect(decodeEvent(message('token', { text: 'في عام ' }))).toEqual({
      type: 'token',
      text: 'في عام ',
    });
  });

  it('skips unknown and malformed progress events', () => {
    expect(decodeEvent(message('stage', { stage: 'thinking' }))).toBeNull();
    expect(decodeEvent(message('stage', { stage: 'queued' }))).toBeNull();
    expect(decodeEvent(message('eta', { expected_seconds: -3 }))).toBeNull();
    expect(decodeEvent(message('token', { text: 7 }))).toBeNull();
    expect(decodeEvent({ event: 'token', data: 'not json' })).toBeNull();
    expect(decodeEvent(message('heartbeat', {}))).toBeNull();
  });

  it('throws an error event as its code and params, never as prose', () => {
    const error = (() => {
      try {
        decodeEvent(message('error', { error: { code: 'LLM_UNAVAILABLE', params: { s: 1 } } }));
      } catch (e) {
        return e;
      }
    })();
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: 'LLM_UNAVAILABLE', params: { s: 1 } });
    expect(() => decodeEvent(message('error', { detail: 'Traceback' }))).toThrow('UNKNOWN_ERROR');
  });

  it('throws on a malformed final rather than showing it', () => {
    expect(() => decodeEvent(message('final', { outcome: 'maybe' }))).toThrow(ApiError);
    expect(() => decodeEvent({ event: 'final', data: '{' })).toThrow(ApiError);
  });
});

describe('decodeAnswer (fails closed)', () => {
  it('keeps a valid answer with its citations', () => {
    expect(decodeAnswer(FINAL_ANSWERED)).toEqual(FINAL_ANSWERED);
  });

  it('turns an answer without a valid citation into a refusal', () => {
    const noCitation = decodeAnswer({ ...FINAL_ANSWERED, citations: [{ rank: 1 }] });
    expect(noCitation).toMatchObject({
      outcome: 'no_answer',
      refusal_reason: 'no_valid_citation',
      answer: null,
      citations: [],
    });
    expect(decodeAnswer({ ...FINAL_ANSWERED, answer: '   ' })?.outcome).toBe('no_answer');
  });

  it('never keeps answer text on a refusal', () => {
    const result = decodeAnswer({ ...FINAL_SENTINEL, answer: 'NO_ANSWER' });
    expect(result).toMatchObject({
      outcome: 'no_answer',
      refusal_reason: 'sentinel',
      answer: null,
    });
  });

  it('reads the refusal reason and nearest documents', () => {
    expect(decodeAnswer(FINAL_GATE)).toEqual(FINAL_GATE);
  });

  it('defaults optional citation fields and drops pages below 1', () => {
    const result = decodeAnswer({
      ...FINAL_ANSWERED,
      citations: [
        { rank: 1, document_id: 'x', page_number: 0 },
        { ...PDF_CITATION, snippet: 1 },
      ],
    });
    expect(result?.citations).toEqual([{ ...PDF_CITATION, snippet: '' }]);
  });
});

describe('streamAsk', () => {
  it('POSTs the question with the CSRF header and hands over events until final', async () => {
    const stream = fakeStream();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(stream.response());
    const events: StreamEvent[] = [];
    const done = streamAsk(
      'ما عدد الفتيات المسجلات؟',
      (e) => events.push(e),
      new AbortController().signal,
    );

    // Split one message across chunks, with a keep-alive ping between events.
    stream.raw('event: stage\ndata: {"stage":"sea');
    stream.raw('rching"}\n\n: ping\n\n');
    stream.send('token', { text: 'In 2021' });
    stream.send('final', FINAL_ANSWERED);
    stream.send('token', { text: ' ignored after final' });
    await done;

    const [url, init] = fetchSpy.mock.calls[0] ?? [];
    expect(url).toBe('/api/ask/stream');
    expect(init?.method).toBe('POST');
    expect(init?.credentials).toBe('same-origin');
    expect(new Headers(init?.headers).get('X-Sanad')).toBe('1');
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json');
    expect(typeof init?.body === 'string' && JSON.parse(init.body)).toEqual({
      question: 'ما عدد الفتيات المسجلات؟',
    });
    expect(events).toEqual([
      { type: 'stage', stage: 'searching' },
      { type: 'token', text: 'In 2021' },
      { type: 'final', result: FINAL_ANSWERED },
    ]);
  });

  it('throws the error envelope of a failed response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'UNAUTHENTICATED', params: {} } }), {
        status: 401,
      }),
    );
    await expect(
      streamAsk('question', () => undefined, new AbortController().signal),
    ).rejects.toMatchObject({ status: 401, code: 'UNAUTHENTICATED' });
  });

  it('throws an error event and stops reading', async () => {
    const stream = fakeStream();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(stream.response());
    const events: StreamEvent[] = [];
    const done = streamAsk('question', (e) => events.push(e), new AbortController().signal);
    stream.raw(
      sse('token', { text: 'partial' }) + sse('error', { error: { code: 'INTERNAL_ERROR' } }),
    );
    await expect(done).rejects.toMatchObject({ code: 'INTERNAL_ERROR' });
    expect(events).toEqual([{ type: 'token', text: 'partial' }]);
  });

  it('treats a stream that ends without final as a network error', async () => {
    const stream = fakeStream();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(stream.response());
    const done = streamAsk('question', () => undefined, new AbortController().signal);
    stream.send('token', { text: 'unvalidated' });
    stream.close();
    await expect(done).rejects.toMatchObject({ status: 0, code: 'NETWORK_ERROR' });
  });

  it('reports an unreachable server as NETWORK_ERROR and rethrows an abort', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(
      streamAsk('question', () => undefined, new AbortController().signal),
    ).rejects.toMatchObject({ code: 'NETWORK_ERROR' });

    const controller = new AbortController();
    controller.abort();
    const abort = new DOMException('Aborted', 'AbortError');
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(abort);
    await expect(streamAsk('question', () => undefined, controller.signal)).rejects.toBe(abort);
  });
});
