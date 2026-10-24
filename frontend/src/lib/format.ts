import type { Language } from '../app/i18n';

/** Digits in the Arabic UI (OPEN_QUESTIONS Q6): Arabic-Indic (١٢٣) or Latin (123). */
export type ArabicNumbering = 'arab' | 'latn';
export const DEFAULT_ARABIC_NUMBERING: ArabicNumbering = 'arab';

export function parseArabicNumbering(value: unknown): ArabicNumbering {
  return value === 'latn' || value === 'arab' ? value : DEFAULT_ARABIC_NUMBERING;
}

/**
 * The BCP 47 tag handed to Intl. The Arabic numbering system is always explicit
 * (-u-nu-arab / -u-nu-latn), so the result never depends on the ICU build's default for `ar`.
 */
export function localeTag(lang: Language, numbering: ArabicNumbering): string {
  return lang === 'ar' ? `ar-u-nu-${numbering}` : 'en';
}

export type DateInput = Date | number | string;

export interface Format {
  readonly locale: string;
  /** A calendar date, e.g. "15 مارس ٢٠٢١" / "Mar 15, 2021". */
  date(value: DateInput, options?: Intl.DateTimeFormatOptions): string;
  /** A date with the time of day. */
  dateTime(value: DateInput, options?: Intl.DateTimeFormatOptions): string;
  number(value: number, options?: Intl.NumberFormatOptions): string;
  /** A ratio as a percentage: 0.25 → "25%" / "٢٥٪". */
  percent(value: number, options?: Intl.NumberFormatOptions): string;
  /** "in 3 days", "yesterday", "قبل ٥ دقائق" … */
  relative(
    value: number,
    unit: Intl.RelativeTimeFormatUnit,
    options?: Intl.RelativeTimeFormatOptions,
  ): string;
  /** `value` relative to `now`, in the largest unit that fits ("5 minutes ago"). */
  since(value: DateInput, now?: DateInput): string;
}

const DATE: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric' };
const DATE_TIME: Intl.DateTimeFormatOptions = { ...DATE, hour: 'numeric', minute: '2-digit' };

const SECOND = 1000;
const STEPS: readonly [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 3600 * SECOND],
  ['month', 30 * 24 * 3600 * SECOND],
  ['week', 7 * 24 * 3600 * SECOND],
  ['day', 24 * 3600 * SECOND],
  ['hour', 3600 * SECOND],
  ['minute', 60 * SECOND],
  ['second', SECOND],
];

function toDate(value: DateInput): Date {
  return value instanceof Date ? value : new Date(value);
}

/** Formatters for one locale. Intl objects are cached per option set. */
export function createFormat(lang: Language, numbering: ArabicNumbering): Format {
  const locale = localeTag(lang, numbering);
  const cache = new Map<
    string,
    Intl.DateTimeFormat | Intl.NumberFormat | Intl.RelativeTimeFormat
  >();

  function cached<T extends Intl.DateTimeFormat | Intl.NumberFormat | Intl.RelativeTimeFormat>(
    kind: string,
    options: object,
    make: () => T,
  ): T {
    const key = `${kind}:${JSON.stringify(options)}`;
    let formatter = cache.get(key) as T | undefined;
    if (!formatter) {
      formatter = make();
      cache.set(key, formatter);
    }
    return formatter;
  }

  const dates = (options: Intl.DateTimeFormatOptions) =>
    cached('dt', options, () => new Intl.DateTimeFormat(locale, options));
  const numbers = (options: Intl.NumberFormatOptions) =>
    cached('nf', options, () => new Intl.NumberFormat(locale, options));
  const relatives = (options: Intl.RelativeTimeFormatOptions) =>
    cached('rt', options, () => new Intl.RelativeTimeFormat(locale, options));

  const relative: Format['relative'] = (value, unit, options = { numeric: 'auto' }) =>
    relatives(options).format(value, unit);

  return {
    locale,
    date: (value, options = DATE) => dates(options).format(toDate(value)),
    dateTime: (value, options = DATE_TIME) => dates(options).format(toDate(value)),
    number: (value, options = {}) => numbers(options).format(value),
    percent: (value, options = {}) =>
      numbers({ style: 'percent', maximumFractionDigits: 1, ...options }).format(value),
    relative,
    since(value, now = Date.now()) {
      const diff = toDate(value).getTime() - toDate(now).getTime();
      const [unit, size] = STEPS.find(([, step]) => Math.abs(diff) >= step) ?? ['second', SECOND];
      return relative(Math.round(diff / size), unit);
    },
  };
}
