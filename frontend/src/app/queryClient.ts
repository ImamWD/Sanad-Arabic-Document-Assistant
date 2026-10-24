import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';

import { sessionQueryKey } from '../features/auth/session';
import { ApiError } from '../lib/api';

const isClientError = (error: unknown) =>
  error instanceof ApiError && error.status >= 400 && error.status < 500;

export function createQueryClient(): QueryClient {
  // A 401 from any request means the session ended (expired, revoked, user deactivated):
  // forget the user, and <RequireAuth> sends them to /login.
  const onError = (error: unknown) => {
    if (error instanceof ApiError && error.status === 401) {
      queryClient.setQueryData(sessionQueryKey, null);
    }
  };
  const queryClient: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: {
        // Retrying a 4xx can't help; network blips and 5xx get one more try.
        retry: (failures, error) => !isClientError(error) && failures < 1,
        refetchOnWindowFocus: false,
      },
    },
  });
  return queryClient;
}
