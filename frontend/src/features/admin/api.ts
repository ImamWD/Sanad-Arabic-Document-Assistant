import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';

import { ApiError, apiFetch } from '../../lib/api';
import type { AdminUser, NewUser, UserChanges } from './types';

export const adminUsersKey = ['admin', 'users'] as const;

// No language in the key, so a language switch never refetches the list. Saves update the
// cached list from the server's answer instead of fetching it again.
export const adminUsersQuery = queryOptions({
  queryKey: adminUsersKey,
  queryFn: ({ signal }) => apiFetch<AdminUser[]>('/admin/users', { signal }),
});

export function createUser(user: NewUser): Promise<AdminUser> {
  return apiFetch<AdminUser>('/admin/users', { method: 'POST', body: user });
}

export function updateUser(id: string, changes: UserChanges): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/admin/users/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: changes,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createUser,
    // The variables hold the new password: drop them once the form unmounts.
    gcTime: 0,
    onSuccess: (user) => {
      queryClient.setQueryData(adminUsersQuery.queryKey, (users) => users && [...users, user]);
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, changes }: { id: string; changes: UserChanges }) => updateUser(id, changes),
    onSuccess: (user) => {
      queryClient.setQueryData(adminUsersQuery.queryKey, (users) =>
        users?.map((each) => (each.id === user.id ? user : each)),
      );
    },
  });
}

const FIELD_OF_CODE: Partial<Record<string, string>> = {
  EMAIL_TAKEN: 'email',
  PASSWORD_TOO_SHORT: 'password',
};

/**
 * The form fields a failed request blames: the field of a coded error, or the body fields of
 * a VALIDATION_ERROR (`params.fields` such as "body.email").
 */
export function invalidFields(error: unknown): ReadonlySet<string> {
  if (!(error instanceof ApiError)) return new Set();
  const field = FIELD_OF_CODE[error.code];
  if (field) return new Set([field]);
  const { fields } = error.params;
  if (error.code !== 'VALIDATION_ERROR' || !Array.isArray(fields)) return new Set();
  return new Set(
    fields
      .filter((path): path is string => typeof path === 'string' && path.startsWith('body.'))
      .map((path) => path.slice('body.'.length)),
  );
}
