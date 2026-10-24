import { type DragEvent, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ApiError } from '../../lib/api';
import { Bidi } from '../../lib/BidiText';
import { cx } from '../../lib/cx';
import { Icon } from '../../lib/Icon';
import { useErrorMessage } from '../../lib/useErrorMessage';
import { useFormat } from '../../lib/useFormat';
import { viewerPath } from '../library/api';
import { MAX_YEAR, MIN_YEAR, parseYear } from '../library/filters';
import { programmeName, useProgrammes } from '../library/labels';
import { DocumentStatus } from '../library/StatusBadge';
import type { Category, UploadDetails } from '../library/types';
import { CATEGORIES } from '../library/types';
import styles from './UploadPage.module.css';
import { type UploadItem, useUploads } from './useUploads';

const ACCEPT = '.pdf,.docx,.txt,application/pdf,text/plain';

function BatchDetails({
  details,
  yearText,
  yearInvalid,
  onChange,
  onYearText,
}: {
  details: UploadDetails;
  yearText: string;
  yearInvalid: boolean;
  onChange: (change: Partial<UploadDetails>) => void;
  onYearText: (text: string) => void;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const { programmes, lang } = useProgrammes();
  const ids = { category: useId(), year: useId(), yearError: useId(), programme: useId() };
  return (
    <fieldset className={styles.details}>
      <legend className={styles.legend}>{t('upload.details.legend')}</legend>
      <p className={styles.hint}>{t('upload.details.hint')}</p>
      <div className={styles.fields}>
        <div className={styles.field}>
          <label htmlFor={ids.category}>{t('upload.details.category')}</label>
          <select
            id={ids.category}
            value={details.category ?? ''}
            onChange={(event) => {
              onChange({ category: (event.target.value || null) as Category | null });
            }}
          >
            <option value="">{t('upload.details.uncategorised')}</option>
            {CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {t(`documents.category.${category}`)}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <label htmlFor={ids.year}>{t('upload.details.year')}</label>
          <input
            id={ids.year}
            className={styles.year}
            type="number"
            inputMode="numeric"
            min={MIN_YEAR}
            max={MAX_YEAR}
            value={yearText}
            aria-invalid={yearInvalid}
            aria-describedby={yearInvalid ? ids.yearError : undefined}
            onChange={(event) => {
              onYearText(event.target.value);
            }}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor={ids.programme}>{t('upload.details.programme')}</label>
          <select
            id={ids.programme}
            value={details.programmeId ?? ''}
            onChange={(event) => {
              onChange({ programmeId: event.target.value || null });
            }}
          >
            <option value="">{t('upload.details.noProgramme')}</option>
            {programmes.map((programme) => (
              <option key={programme.id} value={programme.id}>
                {programmeName(programme, lang)}
              </option>
            ))}
          </select>
        </div>
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={details.restricted}
            onChange={(event) => {
              onChange({ restricted: event.target.checked });
            }}
          />
          {t('upload.details.restricted')}
        </label>
      </div>
      {yearInvalid && (
        <p id={ids.yearError} className={styles.problem} role="alert">
          {t('library.edit.yearInvalid', {
            min: format.number(MIN_YEAR, { useGrouping: false }),
            max: format.number(MAX_YEAR, { useGrouping: false }),
          })}
        </p>
      )}
    </fieldset>
  );
}

function FileRow({ item }: { item: UploadItem }) {
  const { t } = useTranslation();
  const format = useFormat();
  const errorMessage = useErrorMessage();
  const size = format.number(item.file.size / 1024, {
    style: 'unit',
    unit: 'kilobyte',
    maximumFractionDigits: 0,
  });

  let state;
  if (item.phase === 'waiting') {
    state = <span className={styles.muted}>{t('upload.list.waiting')}</span>;
  } else if (item.phase === 'uploading') {
    state = (
      <span className={styles.progress}>
        <progress
          max={1}
          value={item.progress}
          aria-label={t('upload.list.progress', { name: item.file.name })}
        />
        <span>{t('upload.list.uploading', { percent: format.percent(item.progress) })}</span>
      </span>
    );
  } else if (item.phase === 'rejected') {
    const duplicateOf =
      item.error instanceof ApiError && item.error.code === 'DUPLICATE_DOCUMENT'
        ? item.error.params.document_id
        : undefined;
    state = (
      <span className={styles.rejected}>
        <span className={styles.reason} data-error-code={(item.error as ApiError | null)?.code}>
          {errorMessage(item.error)}
        </span>
        {typeof duplicateOf === 'string' && (
          <Link className={styles.link} to={viewerPath(duplicateOf)}>
            {t('upload.list.openExisting')}
          </Link>
        )}
      </span>
    );
  } else if (item.document) {
    state = (
      <span className={styles.server}>
        {item.document.status === 'queued' ? (
          <span className={styles.muted}>{t('upload.list.uploaded')}</span>
        ) : (
          <DocumentStatus document={item.document} />
        )}
        {item.document.status === 'ready' && (
          <Link className={styles.link} to={viewerPath(item.document.id)}>
            {t('upload.list.open')}
          </Link>
        )}
      </span>
    );
  }

  const settled = item.phase === 'rejected' ? 'failed' : (item.document?.status ?? item.phase);
  return (
    <li className={styles.row} data-upload-state={settled}>
      <span className={styles.name}>
        <Bidi text={item.file.name} />
        <span className={styles.size}>{size}</span>
      </span>
      {state}
    </li>
  );
}

/** Upload (F3, editor+): several files, one request each, three at a time. */
export function UploadPage() {
  const { t } = useTranslation();
  const format = useFormat();
  const { rows, addFiles } = useUploads();
  const [details, setDetails] = useState<UploadDetails>({
    category: null,
    year: null,
    programmeId: null,
    restricted: false,
  });
  const [yearText, setYearText] = useState('');
  const [dragging, setDragging] = useState(false);
  const inputId = useId();
  const hintId = useId();
  const listId = useId();
  const yearInvalid = yearText.trim() !== '' && parseYear(yearText) === null;

  const add = (files: FileList | null) => {
    if (!files || files.length === 0 || yearInvalid) return;
    addFiles(Array.from(files), details);
  };

  const onDrag = (event: DragEvent<HTMLDivElement>, over: boolean) => {
    event.preventDefault();
    setDragging(over && !yearInvalid);
  };

  const ready = rows.filter((row) => row.document?.status === 'ready').length;
  const failed = rows.filter(
    (row) => row.phase === 'rejected' || row.document?.status === 'failed',
  ).length;

  return (
    <section className={styles.page}>
      <h1 className={styles.title}>{t('pages.upload.title')}</h1>
      <p className={styles.intro}>{t('upload.intro')}</p>

      <BatchDetails
        details={details}
        yearText={yearText}
        yearInvalid={yearInvalid}
        onChange={(change) => {
          setDetails((current) => ({ ...current, ...change }));
        }}
        onYearText={(text) => {
          setYearText(text);
          setDetails((current) => ({ ...current, year: parseYear(text) }));
        }}
      />

      <div
        className={cx(styles.drop, dragging && styles.dragging)}
        onDragEnter={(event) => {
          onDrag(event, true);
        }}
        onDragOver={(event) => {
          onDrag(event, true);
        }}
        onDragLeave={(event) => {
          onDrag(event, false);
        }}
        onDrop={(event) => {
          onDrag(event, false);
          add(event.dataTransfer.files);
        }}
      >
        <Icon name="upload" />
        <p className={styles.dropLabel}>
          {dragging ? t('upload.drop.active') : t('upload.drop.label')}
        </p>
        <input
          id={inputId}
          className={styles.fileInput}
          type="file"
          multiple
          accept={ACCEPT}
          disabled={yearInvalid}
          aria-describedby={hintId}
          onChange={(event) => {
            add(event.target.files);
            // Choosing the same file again still fires a change.
            event.target.value = '';
          }}
        />
        <label htmlFor={inputId} className={cx(styles.choose, yearInvalid && styles.disabled)}>
          {t('upload.drop.choose')}
        </label>
        <p id={hintId} className={styles.hint}>
          {t('upload.drop.hint')}
        </p>
      </div>

      {rows.length > 0 && (
        <section className={styles.list} aria-labelledby={listId}>
          <h2 id={listId} className={styles.listHeading}>
            {t('upload.list.heading')}
          </h2>
          <p className={styles.summary} aria-live="polite">
            {t('upload.list.summary', {
              ready: format.number(ready),
              total: format.number(rows.length),
              failed: format.number(failed),
            })}
          </p>
          <ul className={styles.rows}>
            {rows.map((item) => (
              <FileRow key={item.key} item={item} />
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}
