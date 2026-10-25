import { useCallback, useLayoutEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router';

import type { LibraryFilters } from './types';
import { CATEGORIES, FILE_TYPES, STATUSES } from './types';

export const MIN_YEAR = 1900;
export const MAX_YEAR = 2100;

function oneOf<T extends string>(value: string | null, options: readonly T[]): T | null {
  return options.includes(value as T) ? (value as T) : null;
}

export function parseYear(value: string | null): number | null {
  if (value === null || !/^\d{4}$/.test(value.trim())) return null;
  const year = Number(value);
  return year >= MIN_YEAR && year <= MAX_YEAR ? year : null;
}

function parsePage(value: string | null): number {
  const page = Number(value);
  return Number.isInteger(page) && page >= 1 ? page : 1;
}

/**
 * Filters live in the URL (?q=…&category=…), so they survive a language switch, a reload and
 * the back button, and a filtered Library can be shared as a link. Unknown values are ignored.
 */
export function filtersFromParams(params: URLSearchParams): LibraryFilters {
  const category = params.get('category');
  const access = params.get('access');
  return {
    q: params.get('q') ?? '',
    fileType: oneOf(params.get('type'), FILE_TYPES),
    category: category === 'none' ? 'none' : oneOf(category, CATEGORIES),
    yearFrom: parseYear(params.get('from')),
    yearTo: parseYear(params.get('to')),
    programmeId: params.get('programme') ?? null,
    status: oneOf(params.get('status'), STATUSES),
    access: access === 'restricted' || access === 'open' ? access : null,
    includeArchived: params.get('archived') === '1',
    page: parsePage(params.get('page')),
  };
}

export function filtersToParams(filters: LibraryFilters): URLSearchParams {
  const params = new URLSearchParams();
  const set = (key: string, value: string | number | null) => {
    if (value !== null && value !== '') params.set(key, String(value));
  };
  set('q', filters.q.trim());
  set('type', filters.fileType);
  set('category', filters.category);
  set('from', filters.yearFrom);
  set('to', filters.yearTo);
  set('programme', filters.programmeId);
  set('status', filters.status);
  set('access', filters.access);
  if (filters.includeArchived) params.set('archived', '1');
  if (filters.page > 1) params.set('page', String(filters.page));
  return params;
}

export function hasActiveFilters(filters: LibraryFilters): boolean {
  return filtersToParams({ ...filters, page: 1 }).size > 0;
}

/** The Library's filters, read from and written to the URL. */
export function useLibraryFilters() {
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => filtersFromParams(params), [params]);

  // The router renders each navigation in a transition, so a second change can arrive before
  // the first is on screen (Clear filters, then a year typed at once), even through a handler
  // from an older render. Each change therefore starts from the newest query string asked
  // for, kept in refs, not from a render's params; otherwise the second change would bring
  // back what the first one removed.
  const shown = useRef(params.toString());
  const pending = useRef<string[]>([]);
  useLayoutEffect(() => {
    shown.current = params.toString();
    const index = pending.current.indexOf(shown.current);
    // Ours: drop it and anything older. Not ours (the back button): start from the URL.
    pending.current = index >= 0 ? pending.current.slice(index + 1) : [];
  }, [params]);

  /** Change some filters; any change other than the page goes back to page 1. */
  const update = useCallback(
    (change: Partial<LibraryFilters>) => {
      const current = new URLSearchParams(pending.current.at(-1) ?? shown.current);
      const out = filtersToParams({ ...filtersFromParams(current), page: 1, ...change });
      // Keep anything else in the URL (?lang= and so on).
      for (const [key, value] of current) {
        if (!KNOWN_KEYS.has(key)) out.set(key, value);
      }
      pending.current = [...pending.current, out.toString()];
      setParams(out, { replace: true });
    },
    [setParams],
  );

  return { filters, update };
}

const KNOWN_KEYS = new Set([
  'q',
  'type',
  'category',
  'from',
  'to',
  'programme',
  'status',
  'access',
  'archived',
  'page',
]);
