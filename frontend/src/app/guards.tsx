import { useTranslation } from 'react-i18next';
import { Navigate, Outlet, useLocation } from 'react-router';

import { hasRole } from '../features/auth/roles';
import {
  CurrentUserContext,
  useCurrentUser,
  useSession,
  useSessionEnded,
} from '../features/auth/session';
import type { Role } from '../features/auth/types';
import styles from './guards.module.css';
import { ForbiddenPage } from './pages';

function SessionLoading() {
  const { t } = useTranslation();
  return (
    <p role="status" className={styles.loading}>
      {t('common.loading')}
    </p>
  );
}

/**
 * Routes for signed-in users. A visitor without a session goes to /login and comes back to
 * this page afterwards; after a sign-out (or an expired session) /login starts fresh at Ask,
 * so the next person doesn't land on the previous user's page.
 */
export function RequireAuth() {
  const { data: user, isPending } = useSession();
  const ended = useSessionEnded();
  const location = useLocation();
  if (isPending) return <SessionLoading />;
  if (!user) return <Navigate to="/login" replace state={ended ? null : { from: location }} />;
  return (
    <CurrentUserContext value={user}>
      <Outlet />
    </CurrentUserContext>
  );
}

/** Routes for `minimum` and above. Nested inside <RequireAuth>. */
export function RequireRole({ minimum }: { minimum: Role }) {
  const user = useCurrentUser();
  return hasRole(user, minimum) ? <Outlet /> : <ForbiddenPage />;
}
