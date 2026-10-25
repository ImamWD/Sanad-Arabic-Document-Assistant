import { useQuery } from '@tanstack/react-query';
import { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { currentLanguage } from '../../app/i18n';
import { ApiError } from '../../lib/api';
import { useErrorMessage } from '../../lib/useErrorMessage';
import { programmesQuery } from './api';
import type { DocumentItem, Programme } from './types';

/** A programme's name in the UI language. */
export function programmeName(programme: Programme, lang: 'ar' | 'en'): string {
  return lang === 'ar' ? programme.name_ar : programme.name_en;
}

/**
 * Programmes for filters and labels. The names are picked by the UI language at render time,
 * so a language switch relabels them without a request.
 */
export function useProgrammes() {
  const { i18n } = useTranslation();
  const lang = currentLanguage(i18n);
  const query = useQuery(programmesQuery);
  const programmes = useMemo(() => query.data ?? [], [query.data]);
  const nameOf = useCallback(
    (id: string | null) => {
      if (!id) return null;
      const programme = programmes.find((p) => p.id === id);
      return programme ? programmeName(programme, lang) : null;
    },
    [programmes, lang],
  );
  return { programmes, nameOf, lang };
}

/**
 * Why a document failed, through the same `errors.<CODE>` translations as every other error:
 * NO_TEXT_LAYER reads "this file has no text layer (scanned image)". Unknown codes are generic.
 */
export function useFailureReason(): (
  document: Pick<DocumentItem, 'error_code' | 'error_params'>,
) => string {
  const errorMessage = useErrorMessage();
  return useCallback(
    (document) =>
      errorMessage(new ApiError(0, document.error_code ?? '', document.error_params ?? {})),
    [errorMessage],
  );
}
