import { useTranslation } from 'react-i18next';

import styles from './App.module.css';
import { currentLanguage, type Language } from './i18n';

const OTHER_LANGUAGE: Record<Language, Language> = { ar: 'en', en: 'ar' };

export function App() {
  const { t, i18n } = useTranslation();
  const target = OTHER_LANGUAGE[currentLanguage(i18n)];

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <h1 className={styles.title}>{t('app.title')}</h1>
        <button
          type="button"
          className={styles.langSwitch}
          lang={target}
          onClick={() => void i18n.changeLanguage(target)}
        >
          {t('language.switch')}
        </button>
      </header>
    </div>
  );
}
