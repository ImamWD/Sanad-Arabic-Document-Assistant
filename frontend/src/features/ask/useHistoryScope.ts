import { useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { sessionQueryKey } from '../auth/session';
import { queriesKey } from './api';

/**
 * The session the cached history belongs to. Every sign-in, guest sign-in, sign-out or 401
 * replaces the session data, so the scope changes with it. History queries are keyed by the
 * scope and older scopes are dropped: after a new guest login (or another user's), nothing
 * from the previous session can flash on screen. The server scopes the guest's history to
 * its session too (ROADMAP R1); this only keeps the browser cache in step.
 */
export function useHistoryScope(): number {
  const queryClient = useQueryClient();
  // Read, not subscribed (like useSessionEnded): a session change remounts the Ask page.
  const scope = queryClient.getQueryState(sessionQueryKey)?.dataUpdateCount ?? 0;

  useEffect(() => {
    queryClient.removeQueries({
      queryKey: queriesKey,
      predicate: (query) => query.queryKey[1] !== scope,
    });
  }, [queryClient, scope]);

  return scope;
}
