import { type ReactNode, useId } from 'react';
import { useTranslation } from 'react-i18next';

import { hasRole } from '../auth/roles';
import { useCurrentUser } from '../auth/session';
import { hasActiveFilters, MAX_YEAR, MIN_YEAR, parseYear } from './filters';
import { programmeName, useProgrammes } from './labels';
import styles from './LibraryFilters.module.css';
import type { Category, DocStatus, FileType, LibraryFilters as Filters } from './types';
import { CATEGORIES, FILE_TYPES, STATUSES } from './types';
import { useDraft } from './useDraft';

const SEARCH_DELAY_MS = 300;

interface LibraryFiltersProps {
  filters: Filters;
  onChange: (change: Partial<Filters>) => void;
}

function YearField({
  label,
  value,
  onCommit,
}: {
  label: string;
  value: number | null;
  onCommit: (year: number | null) => void;
}) {
  const id = useId();
  // Only a complete year (or an empty field) reaches the URL; "20" on the way to "2021" waits.
  const [draft, setDraft] = useDraft(value === null ? '' : String(value), (text) => {
    if (text.trim() === '') onCommit(null);
    else {
      const year = parseYear(text);
      if (year !== null) onCommit(year);
    }
  });
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        className={styles.year}
        type="number"
        inputMode="numeric"
        min={MIN_YEAR}
        max={MAX_YEAR}
        value={draft}
        onChange={(event) => {
          setDraft(event.target.value);
        }}
      />
    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  const id = useId();
  // The URL changes in a transition; the field shows the choice at once in the meantime.
  const [draft, setDraft] = useDraft(value, onChange);
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        value={draft}
        onChange={(event) => {
          setDraft(event.target.value);
        }}
      >
        {children}
      </select>
    </div>
  );
}

/** Search and filters. Every value lives in the URL, so none is lost on a language switch. */
export function LibraryFilters({ filters, onChange }: LibraryFiltersProps) {
  const { t } = useTranslation();
  const user = useCurrentUser();
  const { programmes, lang } = useProgrammes();
  const searchId = useId();
  const [search, setSearch] = useDraft(
    filters.q,
    (q) => {
      onChange({ q });
    },
    SEARCH_DELAY_MS,
  );
  const [archived, setArchived] = useDraft(filters.includeArchived ? '1' : '', (value) => {
    onChange({ includeArchived: value === '1' });
  });
  const any = <option value="">{t('library.filters.any')}</option>;

  return (
    <div className={styles.bar}>
      <div className={styles.search}>
        <label htmlFor={searchId}>{t('library.search.label')}</label>
        <input
          id={searchId}
          type="search"
          dir="auto"
          value={search}
          placeholder={t('library.search.placeholder')}
          onChange={(event) => {
            setSearch(event.target.value);
          }}
        />
      </div>

      <fieldset className={styles.filters}>
        <legend className={styles.legend}>{t('library.filters.label')}</legend>
        <SelectField
          label={t('library.filters.fileType')}
          value={filters.fileType ?? ''}
          onChange={(value) => {
            onChange({ fileType: (value || null) as FileType | null });
          }}
        >
          {any}
          {FILE_TYPES.map((type) => (
            <option key={type} value={type}>
              {t(`documents.fileType.${type}`)}
            </option>
          ))}
        </SelectField>

        <SelectField
          label={t('library.filters.category')}
          value={filters.category ?? ''}
          onChange={(value) => {
            onChange({ category: (value || null) as Category | 'none' | null });
          }}
        >
          {any}
          {CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {t(`documents.category.${category}`)}
            </option>
          ))}
          <option value="none">{t('library.filters.uncategorised')}</option>
        </SelectField>

        <YearField
          label={t('library.filters.yearFrom')}
          value={filters.yearFrom}
          onCommit={(yearFrom) => {
            onChange({ yearFrom });
          }}
        />
        <YearField
          label={t('library.filters.yearTo')}
          value={filters.yearTo}
          onCommit={(yearTo) => {
            onChange({ yearTo });
          }}
        />

        <SelectField
          label={t('library.filters.programme')}
          value={filters.programmeId ?? ''}
          onChange={(value) => {
            onChange({ programmeId: value || null });
          }}
        >
          {any}
          {programmes.map((programme) => (
            <option key={programme.id} value={programme.id}>
              {programmeName(programme, lang)}
            </option>
          ))}
        </SelectField>

        <SelectField
          label={t('library.filters.status')}
          value={filters.status ?? ''}
          onChange={(value) => {
            onChange({ status: (value || null) as DocStatus | null });
          }}
        >
          {any}
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {t(`documents.status.${status}`)}
            </option>
          ))}
        </SelectField>

        {hasRole(user, 'editor') && (
          <SelectField
            label={t('library.filters.access')}
            value={filters.access ?? ''}
            onChange={(value) => {
              onChange({ access: value === 'restricted' || value === 'open' ? value : null });
            }}
          >
            {any}
            <option value="restricted">{t('library.filters.accessRestricted')}</option>
            <option value="open">{t('library.filters.accessOpen')}</option>
          </SelectField>
        )}

        <label className={styles.check}>
          <input
            type="checkbox"
            checked={archived === '1'}
            onChange={(event) => {
              setArchived(event.target.checked ? '1' : '');
            }}
          />
          {t('library.filters.includeArchived')}
        </label>

        {hasActiveFilters(filters) && (
          <button
            type="button"
            className={styles.clear}
            onClick={() => {
              onChange({
                q: '',
                fileType: null,
                category: null,
                yearFrom: null,
                yearTo: null,
                programmeId: null,
                status: null,
                access: null,
                includeArchived: false,
              });
            }}
          >
            {t('library.filters.clear')}
          </button>
        )}
      </fieldset>
    </div>
  );
}
