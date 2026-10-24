import { useTranslation } from 'react-i18next';

import { Icon } from '../lib/Icon';
import { currentLanguage, type Language } from './i18n';
import styles from './LanguageSwitch.module.css';

const OTHER_LANGUAGE: Record<Language, Language> = { ar: 'en', en: 'ar' };

/**
 * Switches the UI to the other language. Only i18n state changes (both locales are bundled),
 * so nothing is refetched and no request is made.
 */
export function LanguageSwitch() {
  const { t, i18n } = useTranslation();
  const target = OTHER_LANGUAGE[currentLanguage(i18n)];

  return (
    <button
      type="button"
      className={styles.switch}
      lang={target}
      onClick={() => void i18n.changeLanguage(target)}
    >
      <Icon name="globe" />
      {t('language.switch')}
    </button>
  );
}
