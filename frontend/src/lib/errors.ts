import en from '../locales/en.json';
import { ApiError, UNKNOWN_ERROR } from './api';

/** An error code with an `errors.<CODE>` translation (both locales have the same keys). */
export type TranslatedErrorCode = keyof typeof en.errors;

export function isTranslatedErrorCode(code: string): code is TranslatedErrorCode {
  return Object.hasOwn(en.errors, code);
}

/** The code to show for any thrown value. Unknown codes and non-API errors are generic. */
export function errorCodeOf(error: unknown): TranslatedErrorCode {
  if (error instanceof ApiError && isTranslatedErrorCode(error.code)) return error.code;
  return UNKNOWN_ERROR;
}
