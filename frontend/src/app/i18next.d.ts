// Typed translation keys: t('app.title') compiles, t('app.typo') does not.
import 'i18next';

import type en from '../locales/en.json';

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation';
    resources: { translation: typeof en };
  }
}
