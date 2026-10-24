import { describe, expect, it } from 'vitest';

import { type AskAction, askReducer, type AskState, IDLE } from './askState';
import { FINAL_ANSWERED, FINAL_SENTINEL } from './test-fixtures';
import type { StreamEvent } from './types';

const QUESTION = 'How many girls enrolled in 2021?';

function run(...events: StreamEvent[]): AskState {
  let state = askReducer(IDLE, { type: 'submitted', question: QUESTION });
  events.forEach((event, i) => {
    state = askReducer(state, { type: 'event', event, at: 1000 * (i + 1) });
  });
  return state;
}

describe('askReducer', () => {
  it('shows a local stage the moment a question is sent', () => {
    expect(run()).toMatchObject({ phase: 'streaming', question: QUESTION, stage: 'starting' });
  });

  it('follows the stages and keeps the band from the reading stage on', () => {
    const state = run(
      { type: 'stage', stage: 'searching' },
      { type: 'stage', stage: 'reading', sources: 6, band: 'low_confidence' },
      { type: 'stage', stage: 'queued', position: 2 },
    );
    expect(state).toMatchObject({ stage: 'queued', position: 2, sources: 6 });
    expect(state).toMatchObject({ band: 'low_confidence' });
  });

  it('times the estimate from when it arrived', () => {
    expect(
      run({ type: 'stage', stage: 'searching' }, { type: 'eta', expectedSeconds: 45 }),
    ).toMatchObject({
      eta: { expectedSeconds: 45, since: 2000 },
    });
  });

  it('treats the first token as writing, and a late stage cannot take it back', () => {
    const state = run(
      { type: 'stage', stage: 'reading', sources: 4, band: 'answer' },
      { type: 'token', text: 'In 2021 ' },
      { type: 'stage', stage: 'reading', sources: 4, band: 'answer' },
      { type: 'token', text: 'the programme' },
    );
    expect(state).toMatchObject({ stage: 'writing', text: 'In 2021 the programme' });
  });

  it('replaces the streamed text with the validated answer', () => {
    const state = run(
      { type: 'token', text: 'unvalidated draft' },
      { type: 'final', result: FINAL_ANSWERED },
    );
    expect(state).toEqual({
      phase: 'done',
      question: QUESTION,
      result: FINAL_ANSWERED,
      askedAt: null,
    });
  });

  it('drops the streamed text when the outcome is a refusal', () => {
    const state = run(
      { type: 'token', text: 'The figure was' },
      { type: 'final', result: FINAL_SENTINEL },
    );
    expect(state).toEqual({
      phase: 'done',
      question: QUESTION,
      result: FINAL_SENTINEL,
      askedAt: null,
    });
    expect(JSON.stringify(state)).not.toContain('The figure was');
  });

  it('drops the streamed text on an error', () => {
    const streaming = run({ type: 'token', text: 'half an answer' });
    const failed = askReducer(streaming, {
      type: 'failed',
      error: { code: 'NETWORK_ERROR', params: {} },
    });
    expect(failed).toEqual({
      phase: 'failed',
      question: QUESTION,
      error: { code: 'NETWORK_ERROR', params: {} },
    });
  });

  it('ignores events once the answer is final, and failures outside a stream', () => {
    const done = run({ type: 'final', result: FINAL_ANSWERED });
    const late: AskAction[] = [
      { type: 'event', event: { type: 'token', text: 'late' }, at: 9000 },
      { type: 'failed', error: { code: 'UNKNOWN_ERROR', params: {} } },
    ];
    expect(late.reduce(askReducer, done)).toBe(done);
  });

  it('shows a stored answer from the history', () => {
    const state = askReducer(run({ type: 'token', text: 'x' }), {
      type: 'showStored',
      question: 'سؤال سابق',
      result: FINAL_ANSWERED,
      askedAt: '2026-10-20T09:30:00Z',
    });
    expect(state).toEqual({
      phase: 'done',
      question: 'سؤال سابق',
      result: FINAL_ANSWERED,
      askedAt: '2026-10-20T09:30:00Z',
    });
  });
});
