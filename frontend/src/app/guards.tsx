import { useTranslation } from 'react-i18next';
import { Navigate, Outlet, useLocation } from 'react-router';

import { hasRole } from '../features/auth/roles';
import { useCurrentUser, useSession } from '../features/auth/session';
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

/** Routes for signed-in users. Without a session, go to /login and come back afterwards. */
export function RequireAuth() {
  const { data: user, isPending } = useSession();
  const location = useLocation();
  if (isPending) return <SessionLoading />;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}

/** Routes for `minimum` and above. Nested inside <RequireAuth>. */
export function RequireRole({ minimum }: { minimum: Role }) {
  const user = useCurrentUser();
  return hasRole(user, minimum) ? <Outlet /> : <ForbiddenPage />;
}
