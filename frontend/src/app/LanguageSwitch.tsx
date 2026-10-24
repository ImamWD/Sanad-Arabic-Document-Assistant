import { useTranslation } from 'react-i18next';

import { useRememberLanguage } from '../features/auth/session';
import { Icon } from '../lib/Icon';
import { currentLanguage, type Language, markExplicitLanguage } from './i18n';
import styles from './LanguageSwitch.module.css';

const OTHER_LANGUAGE: Record<Language, Language> = { ar: 'en', en: 'ar' };

/**
 * Switches the UI to the other language, which mirrors the whole layout. Only i18n state
 * changes (both locales are bundled), so nothing is refetched (no GET) and on-screen state
 * survives. A signed-in user's choice is saved to their profile (PATCH /api/me).
 */
export function LanguageSwitch() {
  const { t, i18n } = useTranslation();
  const rememberLanguage = useRememberLanguage();
  const target = OTHER_LANGUAGE[currentLanguage(i18n)];

  const switchLanguage = () => {
    markExplicitLanguage();
    void i18n.changeLanguage(target);
    rememberLanguage(target);
  };

  return (
    <button type="button" className={styles.switch} lang={target} onClick={switchLanguage}>
      <Icon name="globe" />
      {t('language.switch')}
    </button>
  );
}
