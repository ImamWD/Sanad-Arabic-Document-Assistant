import { useTranslation } from 'react-i18next';
import { Link, NavLink, Outlet } from 'react-router';

import { useCurrentUser } from '../features/auth/session';
import { Icon } from '../lib/Icon';
import styles from './AppLayout.module.css';
import { LanguageSwitch } from './LanguageSwitch';
import { navItemsFor } from './navigation';
import { UserMenu } from './UserMenu';

/** The signed-in shell: header (name, language, account), navigation by role, page. */
export function AppLayout() {
  const { t } = useTranslation();
  const user = useCurrentUser();

  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#main">
        {t('shell.skipToContent')}
      </a>
      <header className={styles.header}>
        <Link className={styles.brand} to="/ask">
          {t('app.name')}
        </Link>
        <div className={styles.actions}>
          <LanguageSwitch />
          <UserMenu />
        </div>
      </header>
      <div className={styles.body}>
        <nav className={styles.nav} aria-label={t('shell.nav.label')}>
          <ul className={styles.navList}>
            {navItemsFor(user).map((item) => (
              <li key={item.id}>
                <NavLink className={styles.navLink ?? ''} to={item.path}>
                  <Icon name={item.icon} />
                  {t(`shell.nav.${item.id}`)}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main id="main" className={styles.main} tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
