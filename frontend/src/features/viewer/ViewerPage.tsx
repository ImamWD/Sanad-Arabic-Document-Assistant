import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useParams, useSearchParams } from 'react-router';

import { Bidi } from '../../lib/BidiText';
import { useErrorMessage } from '../../lib/useErrorMessage';
import { useFormat } from '../../lib/useFormat';
import { hasRole } from '../auth/roles';
import { useCurrentUser } from '../auth/session';
import { documentQuery } from '../library/api';
import { useProgrammes } from '../library/labels';
import {
  ArchivedBadge,
  DocumentStatus,
  RestrictedBadge,
  UncategorisedFlag,
} from '../library/StatusBadge';
import type { DocumentItem } from '../library/types';
import { pdfFileQuery } from './api';
import { PdfViewer } from './PdfViewer';
import { usePdfDocument } from './usePdfDocument';
import styles from './ViewerPage.module.css';

/** ?page=N as a page number, or null when it is missing or not a positive integer. */
function citedPageOf(value: string | null): number | null {
  const page = Number(value);
  return value !== null && Number.isInteger(page) && page >= 1 ? page : null;
}

function DocumentDetails({ document }: { document: DocumentItem }) {
  const { t } = useTranslation();
  const format = useFormat();
  const { nameOf } = useProgrammes();
  const notSet = t('documents.notSet');
  const programme = nameOf(document.programme_id);
  return (
    <dl className={styles.details} aria-label={t('viewer.details')}>
      <div>
        <dt>{t('viewer.fileType')}</dt>
        <dd>{t(`documents.fileType.${document.file_type}`)}</dd>
      </div>
      <div>
        <dt>{t('viewer.category')}</dt>
        <dd>
          {document.category ? t(`documents.category.${document.category}`) : <UncategorisedFlag />}
        </dd>
      </div>
      <div>
        <dt>{t('viewer.year')}</dt>
        <dd>
          {document.year === null ? notSet : format.number(document.year, { useGrouping: false })}
        </dd>
      </div>
      <div>
        <dt>{t('viewer.programme')}</dt>
        <dd>{programme ? <Bidi text={programme} /> : notSet}</dd>
      </div>
      <div>
        <dt>{t('viewer.pages')}</dt>
        <dd>{document.page_count === null ? notSet : format.number(document.page_count)}</dd>
      </div>
      <div>
        <dt>{t('viewer.uploaded')}</dt>
        <dd>
          {t('viewer.uploadedBy', {
            name: document.uploaded_by.name,
            date: format.date(document.uploaded_at),
          })}
        </dd>
      </div>
      <div className={styles.wide}>
        <dt>{t('viewer.filename')}</dt>
        <dd>
          <Bidi text={document.original_filename} />
        </dd>
      </div>
    </dl>
  );
}

/** Fetch the PDF rendition and show it. Mounted once per document (keyed by id). */
function DocumentPdf({ id, citedPage }: { id: string; citedPage: number | null }) {
  const { t } = useTranslation();
  const errorMessage = useErrorMessage();
  const file = useQuery(pdfFileQuery(id));
  const pdf = usePdfDocument(file.data);

  if (file.isError) {
    return (
      <p className={styles.error} role="alert">
        {errorMessage(file.error)}
      </p>
    );
  }
  if (pdf.status === 'error') {
    return (
      <p className={styles.error} role="alert">
        {t('viewer.renderFailed')}
      </p>
    );
  }
  if (pdf.status === 'loading') {
    return (
      <p className={styles.message} role="status">
        {t('viewer.loading')}
      </p>
    );
  }
  return <PdfViewer pages={pdf.pages} citedPage={citedPage} />;
}

/** /documents/:id?page=N (F4): the document at the cited page, which is marked. */
export function ViewerPage() {
  const { t } = useTranslation();
  const errorMessage = useErrorMessage();
  const user = useCurrentUser();
  const { id = '' } = useParams();
  const [params] = useSearchParams();
  const citedPage = citedPageOf(params.get('page'));
  const document = useQuery(documentQuery(id));

  let body;
  if (document.isPending) {
    body = (
      <p className={styles.message} role="status">
        {t('viewer.loading')}
      </p>
    );
  } else if (document.isError) {
    body = (
      <p className={styles.error} role="alert">
        {errorMessage(document.error)}
      </p>
    );
  } else {
    const doc = document.data;
    body = (
      <>
        <header className={styles.header}>
          <Bidi as="h1" className={styles.title} text={doc.title} />
          {((hasRole(user, 'editor') && doc.restricted) || doc.is_archived) && (
            <div className={styles.badges}>
              {hasRole(user, 'editor') && doc.restricted && <RestrictedBadge />}
              {doc.is_archived && <ArchivedBadge />}
            </div>
          )}
          <DocumentDetails document={doc} />
          {doc.is_converted && (
            <p className={styles.converted} role="note">
              {doc.file_type === 'docx' ? t('viewer.convertedWord') : t('viewer.convertedOther')}
            </p>
          )}
        </header>
        {doc.status === 'ready' ? (
          <DocumentPdf key={doc.id} id={doc.id} citedPage={citedPage} />
        ) : (
          <div className={styles.notReady}>
            <p className={styles.message}>
              {doc.status === 'failed' ? t('viewer.failed') : t('viewer.notReady')}
            </p>
            <DocumentStatus document={doc} />
          </div>
        )}
      </>
    );
  }

  return (
    <section className={styles.page}>
      <Link className={styles.back} to="/library">
        {t('viewer.back')}
      </Link>
      {body}
    </section>
  );
}
