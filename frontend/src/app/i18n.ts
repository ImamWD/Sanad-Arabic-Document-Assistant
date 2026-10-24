import i18next, { type i18n as I18n } from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';

import ar from '../locales/ar.json';
import en from '../locales/en.json';

export const SUPPORTED_LANGUAGES = ['ar', 'en'] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];
// The demo opens in English (BUILD_PLAN: language and presentation).
export const DEFAULT_LANGUAGE: Language = 'en';
export const LANGUAGE_STORAGE_KEY = 'sanad.lang';

export function isLanguage(value: unknown): value is Language {
  return SUPPORTED_LANGUAGES.includes(value as Language);
}

export function currentLanguage(i18n: I18n): Language {
  const lng = i18n.resolvedLanguage;
  return isLanguage(lng) ? lng : DEFAULT_LANGUAGE;
}

/** Mirror the active locale onto <html lang dir> and the document title. */
export function applyDocumentLanguage(i18n: I18n): void {
  const lng = currentLanguage(i18n);
  const root = document.documentElement;
  root.lang = lng;
  root.dir = i18n.dir(lng);
  document.title = i18n.t('app.title');
}

// Whether the language was chosen explicitly on this visit (page load): by ?lang= in the URL
// or with the language switch. An explicit choice beats the user's saved preference
// (ProfileLanguage). Page-level state, reset by initI18n: react-i18next hands components a
// per-render wrapper of the instance, so it can't be keyed on the instance.
let explicitChoice = false;

export function markExplicitLanguage(): void {
  explicitChoice = true;
}

export function hasExplicitLanguage(): boolean {
  return explicitChoice;
}

/**
 * Locale priority (SYSTEM_DESIGN §8): ?lang= in the URL, then the signed-in user's
 * preference (app/ProfileLanguage.tsx), then the last choice in localStorage, then English.
 * Both locales are bundled, so switching language never touches the network.
 */
export async function initI18n(i18n: I18n = i18next.createInstance()): Promise<I18n> {
  i18n.on('languageChanged', () => {
    applyDocumentLanguage(i18n);
  });
  await i18n
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
      resources: { ar: { translation: ar }, en: { translation: en } },
      supportedLngs: SUPPORTED_LANGUAGES,
      fallbackLng: DEFAULT_LANGUAGE,
      load: 'languageOnly',
      nonExplicitSupportedLngs: true,
      interpolation: { escapeValue: false },
      detection: {
        order: ['querystring', 'localStorage'],
        lookupQuerystring: 'lang',
        lookupLocalStorage: LANGUAGE_STORAGE_KEY,
        caches: ['localStorage'],
      },
    });
  applyDocumentLanguage(i18n);
  // ?lang=en-GB counts (it resolved to en); an unsupported ?lang=fr fell back, so it doesn't.
  const requested = new URLSearchParams(window.location.search).get('lang');
  explicitChoice = requested?.toLowerCase().split('-')[0] === currentLanguage(i18n);
  return i18n;
}
