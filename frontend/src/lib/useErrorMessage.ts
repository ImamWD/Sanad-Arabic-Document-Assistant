import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError } from './api';
import { errorCodeOf } from './errors';

/** Translate a thrown value through `errors.<CODE>`; server prose is never shown. */
export function useErrorMessage(): (error: unknown) => string {
  const { t } = useTranslation();
  return useCallback(
    (error: unknown) =>
      t(`errors.${errorCodeOf(error)}`, error instanceof ApiError ? { ...error.params } : {}),
    [t],
  );
}
