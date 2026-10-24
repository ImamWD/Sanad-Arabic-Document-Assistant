import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { currentLanguage } from '../app/i18n';
import { AR_NUMBERING } from './config';
import { createFormat, type Format } from './format';

/**
 * Dates, numbers and relative times for the active locale. The only way UI code formats
 * them (CLAUDE.md rule 4): never concatenate or hand-format.
 */
export function useFormat(): Format {
  const { i18n } = useTranslation();
  const lang = currentLanguage(i18n);
  return useMemo(() => createFormat(lang, AR_NUMBERING), [lang]);
}
