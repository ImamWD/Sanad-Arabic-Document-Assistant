import { Outlet } from 'react-router';

import { LanguageSwitch } from './LanguageSwitch';
import styles from './PublicLayout.module.css';

/** Pages before sign-in. The language switch is already there (brief §4: Login). */
export function PublicLayout() {
  return (
    <div className={styles.page}>
      <header className={styles.bar}>
        <LanguageSwitch />
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
