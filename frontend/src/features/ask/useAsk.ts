import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useReducer, useRef } from 'react';

import { ApiError, UNKNOWN_ERROR } from '../../lib/api';
import { sessionQueryKey } from '../auth/session';
import { queriesKey, streamAsk } from './api';
import { askReducer, type AskState, type ErrorInfo, IDLE } from './askState';
import type { StoredQuery, StreamEvent } from './types';

function errorInfo(error: unknown): ErrorInfo {
  return error instanceof ApiError
    ? { code: error.code, params: { ...error.params } }
    : { code: UNKNOWN_ERROR, params: {} };
}

export interface Ask {
  state: AskState;
  ask: (question: string) => void;
  /** Show a question from the history with its stored answer. */
  show: (query: StoredQuery) => void;
}

/**
 * The Ask screen's state and the one stream in flight. A new question, a history item or
 * leaving the page aborts the current stream, and nothing from an aborted stream is shown.
 */
export function useAsk(): Ask {
  const [state, dispatch] = useReducer(askReducer, IDLE);
  const queryClient = useQueryClient();
  const current = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      current.current?.abort();
    },
    [],
  );

  const start = useCallback(() => {
    current.current?.abort();
    const controller = new AbortController();
    current.current = controller;
    return controller.signal;
  }, []);

  const ask = useCallback(
    (question: string) => {
      const signal = start();
      dispatch({ type: 'submitted', question });
      const onEvent = (event: StreamEvent) => {
        if (!signal.aborted) dispatch({ type: 'event', event, at: Date.now() });
      };
      streamAsk(question, onEvent, signal).then(
        () => {
          // The new question is now part of the history.
          void queryClient.invalidateQueries({ queryKey: queriesKey, exact: true });
        },
        (error: unknown) => {
          if (signal.aborted) return;
          // A 401 means the session ended: forget the user, as app/queryClient.ts does for
          // queries, and <RequireAuth> sends them to the login page.
          if (error instanceof ApiError && error.status === 401) {
            queryClient.setQueryData(sessionQueryKey, null);
          }
          dispatch({ type: 'failed', error: errorInfo(error) });
        },
      );
    },
    [queryClient, start],
  );

  const show = useCallback(
    (query: StoredQuery) => {
      start();
      dispatch({
        type: 'showStored',
        question: query.question,
        result: query.result,
        askedAt: query.created_at,
      });
    },
    [start],
  );

  return { state, ask, show };
}
