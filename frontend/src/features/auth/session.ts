import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';

import { currentLanguage, hasExplicitLanguage, type Language } from '../../app/i18n';
import { fetchMe, login, loginAsGuest, logout, savePreferredLanguage } from './api';
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

/**
 * Save `language` to a signed-in user's profile. Fire and forget: a failure (404 until B2
 * lands) never reaches the screen. Never for the guest, a shared account where one visitor's
 * choice would change everyone's.
 */
function rememberLanguage(user: Me | null | undefined, language: Language): void {
  if (!user || user.is_guest) return;
  savePreferredLanguage(language).catch(() => undefined);
}

/** For the language switch: save the new choice if a real user is signed in. */
export function useRememberLanguage(): (language: Language) => void {
  const queryClient = useQueryClient();
  return useCallback(
    // Read at click time, not subscribed: the switch itself never triggers a request for /me.
    (language) => {
      rememberLanguage(queryClient.getQueryData(sessionQueryKey), language);
    },
    [queryClient],
  );
}

function useSignIn<T = void>(mutationFn: (variables: T) => Promise<Me>) {
  const queryClient = useQueryClient();
  const { i18n } = useTranslation();
  return useMutation({
    mutationFn,
    // The login variables hold the password: drop them once the login page unmounts.
    gcTime: 0,
    onSuccess: (me) => {
      queryClient.setQueryData(sessionQueryKey, me);
      // A language chosen on this visit (?lang= or the switch) is kept and saved to the
      // profile. Otherwise <ProfileLanguage> applies the profile's language.
      const language = currentLanguage(i18n);
      if (hasExplicitLanguage() && me.preferred_language !== language) {
        rememberLanguage(me, language);
      }
    },
  });
}

export function useLogin() {
  return useSignIn(login);
}

export function useGuestLogin() {
  return useSignIn(loginAsGuest);
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
