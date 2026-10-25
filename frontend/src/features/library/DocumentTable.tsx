import type { MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { Bidi } from '../../lib/BidiText';
import { useFormat } from '../../lib/useFormat';
import { viewerPath } from './api';
import styles from './DocumentTable.module.css';
import { useProgrammes } from './labels';
import { type RowAction, RowActions } from './RowActions';
import { ArchivedBadge, DocumentStatus, RestrictedBadge, UncategorisedFlag } from './StatusBadge';
import type { DocumentItem } from './types';

interface DocumentTableProps {
  documents: DocumentItem[];
  /** Editors and admins see the restricted badge and the row actions. */
  canEdit: boolean;
  busyId: string | null;
  onAction: (document: DocumentItem, action: RowAction) => void;
}

// The actions menu is portalled, but React still bubbles its clicks up to the row.
const INTERACTIVE = 'a, button, input, select, textarea, [role="menu"]';

export function DocumentTable({ documents, canEdit, busyId, onAction }: DocumentTableProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const navigate = useNavigate();
  const { nameOf } = useProgrammes();
  const notSet = <span className={styles.muted}>{t('documents.notSet')}</span>;

  // A click anywhere on a row opens the document; the title link does the same for the
  // keyboard and screen readers. Clicks on the row's own controls are theirs.
  const openRow = (event: MouseEvent<HTMLTableRowElement>, document: DocumentItem) => {
    if (event.target instanceof Element && event.target.closest(INTERACTIVE)) return;
    void navigate(viewerPath(document.id));
  };

  return (
    <div className={styles.scroller}>
      <table className={styles.table}>
        <caption className={styles.caption}>{t('library.table.caption')}</caption>
        <thead>
          <tr>
            <th scope="col">{t('library.table.title')}</th>
            <th scope="col">{t('library.table.fileType')}</th>
            <th scope="col">{t('library.table.category')}</th>
            <th scope="col">{t('library.table.year')}</th>
            <th scope="col">{t('library.table.programme')}</th>
            <th scope="col">{t('library.table.uploadedBy')}</th>
            <th scope="col">{t('library.table.uploadedAt')}</th>
            <th scope="col">{t('library.table.pages')}</th>
            <th scope="col">{t('library.table.status')}</th>
            {canEdit && (
              <th scope="col">
                <span className={styles.caption}>{t('library.table.actions')}</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => {
            const programme = nameOf(document.programme_id);
            return (
              <tr
                key={document.id}
                className={styles.row}
                data-document-id={document.id}
                onClick={(event) => {
                  openRow(event, document);
                }}
              >
                <td className={styles.titleCell}>
                  <Link className={styles.title} to={viewerPath(document.id)}>
                    <Bidi text={document.title} />
                  </Link>
                  <Bidi as="div" className={styles.filename} text={document.original_filename} />
                  {(canEdit && document.restricted) || document.is_archived ? (
                    <div className={styles.badges}>
                      {canEdit && document.restricted && <RestrictedBadge />}
                      {document.is_archived && <ArchivedBadge />}
                    </div>
                  ) : null}
                </td>
                <td>{t(`documents.fileType.${document.file_type}`)}</td>
                <td>
                  {document.category ? (
                    t(`documents.category.${document.category}`)
                  ) : (
                    <UncategorisedFlag />
                  )}
                </td>
                <td>
                  {document.year === null
                    ? notSet
                    : format.number(document.year, { useGrouping: false })}
                </td>
                <td>{programme ? <Bidi text={programme} /> : notSet}</td>
                <td>
                  <Bidi text={document.uploaded_by.name} />
                </td>
                <td className={styles.nowrap}>{format.date(document.uploaded_at)}</td>
                <td>
                  {document.page_count === null ? notSet : format.number(document.page_count)}
                </td>
                <td>
                  <DocumentStatus document={document} />
                </td>
                {canEdit && (
                  <td>
                    <RowActions
                      document={document}
                      busy={busyId === document.id}
                      onAction={(action) => {
                        onAction(document, action);
                      }}
                    />
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
