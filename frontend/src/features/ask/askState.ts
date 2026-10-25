// What the Ask screen shows, as a pure reducer over stream events. State holds codes and
// payloads only, never translated text, so a language switch re-renders it in place.
import type { AnswerResult, Band, StreamEvent } from './types';

/** `starting` is local: shown the moment the question is sent, before the server answers. */
export type Stage = 'starting' | 'queued' | 'searching' | 'reading' | 'writing';

export interface Eta {
  expectedSeconds: number;
  /** The server capped its estimate (R1d): it is busy, and the real wait is unknown. */
  capped: boolean;
  /** When the estimate arrived (ms since the epoch): elapsed time counts from here. */
  since: number;
}

export interface ErrorInfo {
  code: string;
  params: Record<string, unknown>;
}

export type AskState =
  | { phase: 'idle' }
  | {
      phase: 'streaming';
      question: string;
      stage: Stage;
      position: number | null;
      sources: number | null;
      band: Band | null;
      eta: Eta | null;
      /** Unvalidated: shown while it streams, always replaced or removed at the end. */
      text: string;
    }
  | { phase: 'done'; question: string; result: AnswerResult; askedAt: string | null }
  | { phase: 'failed'; question: string; error: ErrorInfo };

export type AskAction =
  | { type: 'submitted'; question: string }
  | { type: 'event'; event: StreamEvent; at: number }
  | { type: 'failed'; error: ErrorInfo }
  | { type: 'showStored'; question: string; result: AnswerResult; askedAt: string };

export const IDLE: AskState = { phase: 'idle' };

export function askReducer(state: AskState, action: AskAction): AskState {
  switch (action.type) {
    case 'submitted':
      return {
        phase: 'streaming',
        question: action.question,
        stage: 'starting',
        position: null,
        sources: null,
        band: null,
        eta: null,
        text: '',
      };
    case 'showStored':
      return {
        phase: 'done',
        question: action.question,
        result: action.result,
        askedAt: action.askedAt,
      };
    case 'failed':
      // The streamed text goes with the error: it was never validated.
      return state.phase === 'streaming'
        ? { phase: 'failed', question: state.question, error: action.error }
        : state;
    case 'event':
      return state.phase === 'streaming' ? onEvent(state, action.event, action.at) : state;
  }
}

type Streaming = Extract<AskState, { phase: 'streaming' }>;

function onEvent(state: Streaming, event: StreamEvent, at: number): AskState {
  switch (event.type) {
    case 'final':
      // Validation wins over streaming: the validated answer replaces the streamed text, and
      // a refusal removes it.
      return { phase: 'done', question: state.question, result: event.result, askedAt: null };
    case 'token':
      return { ...state, stage: 'writing', text: state.text + event.text };
    case 'eta':
      return {
        ...state,
        eta: { expectedSeconds: event.expectedSeconds, capped: event.capped, since: at },
      };
    case 'stage':
      // Once the answer is being written, a late progress event can't take the stage back.
      if (state.stage === 'writing') return state;
      switch (event.stage) {
        case 'queued':
          return { ...state, stage: 'queued', position: event.position };
        case 'reading':
          return { ...state, stage: 'reading', sources: event.sources, band: event.band };
        default:
          return { ...state, stage: event.stage };
      }
  }
}
