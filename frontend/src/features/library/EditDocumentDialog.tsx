import { type SubmitEvent, useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useErrorMessage } from '../../lib/useErrorMessage';
import { useFormat } from '../../lib/useFormat';
import styles from './EditDocumentDialog.module.css';
import { MAX_YEAR, MIN_YEAR, parseYear } from './filters';
import { programmeName, useProgrammes } from './labels';
import { draftOf, type EditDraft, patchFrom } from './editPatch';
import type { DocumentItem } from './types';
import { CATEGORIES } from './types';
import { useUpdateDocument } from './useDocumentActions';

interface EditDocumentDialogProps {
  document: DocumentItem;
  onClose: () => void;
}

/** Edit title, category, year and programme (PATCH /api/documents/{id}). */
export function EditDocumentDialog({ document, onClose }: EditDocumentDialogProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const errorMessage = useErrorMessage();
  const { programmes, lang } = useProgrammes();
  const update = useUpdateDocument();
  const dialog = useRef<HTMLDialogElement>(null);
  const headingId = useId();
  const ids = {
    title: useId(),
    category: useId(),
    year: useId(),
    yearHint: useId(),
    programme: useId(),
  };
  const [draft, setDraft] = useState(() => draftOf(document));
  const [problem, setProblem] = useState<'title' | 'year' | null>(null);

  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) element.showModal();
    return () => {
      element?.close();
    };
  }, []);

  const set = (field: keyof EditDraft) => (event: { target: { value: string } }) => {
    setDraft((current) => ({ ...current, [field]: event.target.value }));
  };

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!draft.title.trim()) {
      setProblem('title');
      return;
    }
    if (draft.year.trim() !== '' && parseYear(draft.year) === null) {
      setProblem('year');
      return;
    }
    setProblem(null);
    const patch = patchFrom(document, draft);
    if (Object.keys(patch).length === 0) {
      onClose();
      return;
    }
    update.mutate({ id: document.id, patch }, { onSuccess: onClose });
  };

  return (
    <dialog ref={dialog} className={styles.dialog} aria-labelledby={headingId} onClose={onClose}>
      <form className={styles.form} onSubmit={submit} noValidate>
        <h2 id={headingId} className={styles.heading}>
          {t('library.edit.heading')}
        </h2>

        <label htmlFor={ids.title}>{t('library.edit.title')}</label>
        <input
          id={ids.title}
          dir="auto"
          value={draft.title}
          onChange={set('title')}
          aria-invalid={problem === 'title'}
          required
        />
        {problem === 'title' && (
          <p className={styles.problem} role="alert">
            {t('library.edit.titleRequired')}
          </p>
        )}

        <label htmlFor={ids.category}>{t('library.edit.category')}</label>
        <select id={ids.category} value={draft.category} onChange={set('category')}>
          <option value="">{t('library.edit.uncategorised')}</option>
          {CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {t(`documents.category.${category}`)}
            </option>
          ))}
        </select>

        <label htmlFor={ids.year}>{t('library.edit.year')}</label>
        <input
          id={ids.year}
          className={styles.year}
          type="number"
          inputMode="numeric"
          min={MIN_YEAR}
          max={MAX_YEAR}
          value={draft.year}
          onChange={set('year')}
          aria-describedby={ids.yearHint}
          aria-invalid={problem === 'year'}
        />
        <p id={ids.yearHint} className={styles.hint}>
          {t('library.edit.yearHint')}
        </p>
        {problem === 'year' && (
          <p className={styles.problem} role="alert">
            {t('library.edit.yearInvalid', {
              min: format.number(MIN_YEAR, { useGrouping: false }),
              max: format.number(MAX_YEAR, { useGrouping: false }),
            })}
          </p>
        )}

        <label htmlFor={ids.programme}>{t('library.edit.programme')}</label>
        <select id={ids.programme} value={draft.programmeId} onChange={set('programmeId')}>
          <option value="">{t('library.edit.noProgramme')}</option>
          {programmes.map((programme) => (
            <option key={programme.id} value={programme.id}>
              {programmeName(programme, lang)}
            </option>
          ))}
        </select>

        {update.isError && (
          <p className={styles.problem} role="alert">
            {errorMessage(update.error)}
          </p>
        )}

        <div className={styles.buttons}>
          <button type="submit" className={styles.primary} disabled={update.isPending}>
            {update.isPending ? t('library.edit.saving') : t('library.edit.save')}
          </button>
          <button type="button" className={styles.secondary} onClick={onClose}>
            {t('library.edit.cancel')}
          </button>
        </div>
      </form>
    </dialog>
  );
}
