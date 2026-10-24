import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchMe, login, loginAsGuest, logout } from './api';
import type { Me } from './types';

export const sessionQueryKey = ['session'] as const;

// Fetched once per page load. The session changes only through the mutations below (or a
// 401 anywhere, see app/queryClient.ts), so it never goes stale, never retries and never
// refetches on focus: a language switch or a tab change makes no request.
export const sessionQuery = queryOptions({
  queryKey: sessionQueryKey,
  queryFn: fetchMe,
  staleTime: Infinity,
  retry: false,
  refetchOnWindowFocus: false,
});

export function useSession() {
  return useQuery(sessionQuery);
}

/** The signed-in user. Only for components rendered behind <RequireAuth>. */
export function useCurrentUser(): Me {
  const { data } = useSession();
  if (!data) throw new Error('useCurrentUser() outside <RequireAuth>');
  return data;
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: login,
    // The mutation's variables hold the password: drop them once the login page unmounts.
    gcTime: 0,
    onSuccess: (me) => queryClient.setQueryData(sessionQueryKey, me),
  });
}

export function useGuestLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: loginAsGuest,
    onSuccess: (me) => queryClient.setQueryData(sessionQueryKey, me),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logout,
    // Signed out locally even if the request failed: drop every cached document, query and
    // answer, so nothing from this account stays in memory. The session entry is set rather
    // than removed, so the mounted guards don't refetch /me.
    onSettled: () => {
      queryClient.setQueryData(sessionQueryKey, null);
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== sessionQueryKey[0] });
    },
  });
}
