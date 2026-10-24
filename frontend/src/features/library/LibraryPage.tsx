import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useErrorMessage } from '../../lib/useErrorMessage';
import { useFormat } from '../../lib/useFormat';
import { hasRole } from '../auth/roles';
import { useCurrentUser } from '../auth/session';
import { libraryQuery } from './api';
import { DocumentTable } from './DocumentTable';
import { EditDocumentDialog } from './EditDocumentDialog';
import { hasActiveFilters, useLibraryFilters } from './filters';
import { LibraryFilters } from './LibraryFilters';
import styles from './LibraryPage.module.css';
import type { RowAction } from './RowActions';
import type { DocumentItem } from './types';
import { useLifecycle } from './useDocumentActions';

function Pager({
  page,
  pages,
  onPage,
}: {
  page: number;
  pages: number;
  onPage: (page: number) => void;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  if (pages <= 1) return null;
  return (
    <nav className={styles.pager} aria-label={t('library.pager.label')}>
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => {
          onPage(page - 1);
        }}
      >
        {t('library.pager.previous')}
      </button>
      <span>
        {t('library.pager.position', { page: format.number(page), pages: format.number(pages) })}
      </span>
      <button
        type="button"
        disabled={page >= pages}
        onClick={() => {
          onPage(page + 1);
        }}
      >
        {t('library.pager.next')}
      </button>
    </nav>
  );
}

/** The Library (F3): every document the user may see, with filters and editor actions. */
export function LibraryPage() {
  const { t } = useTranslation();
  const format = useFormat();
  const errorMessage = useErrorMessage();
  const user = useCurrentUser();
  const canEdit = hasRole(user, 'editor');
  const { filters, update } = useLibraryFilters();
  const list = useQuery(libraryQuery(filters));
  const lifecycle = useLifecycle();
  const [editing, setEditing] = useState<DocumentItem | null>(null);

  const onAction = (document: DocumentItem, action: RowAction) => {
    lifecycle.reset();
    if (action === 'edit') setEditing(document);
    else lifecycle.mutate({ id: document.id, action });
  };

  let body;
  if (list.isPending) {
    body = <p className={styles.message}>{t('common.loading')}</p>;
  } else if (list.isError) {
    body = (
      <p className={styles.error} role="alert">
        {errorMessage(list.error)}
      </p>
    );
  } else if (list.data.items.length === 0) {
    body = (
      <p className={styles.message}>
        {hasActiveFilters(filters) ? t('library.emptyFiltered') : t('library.empty')}
      </p>
    );
  } else {
    const { items, total, page, page_size: pageSize } = list.data;
    const from = (page - 1) * pageSize + 1;
    body = (
      <>
        <p className={styles.summary} aria-live="polite">
          {t('library.summary', {
            from: format.number(from),
            to: format.number(from + items.length - 1),
            total: format.number(total),
          })}
        </p>
        <DocumentTable
          documents={items}
          canEdit={canEdit}
          busyId={lifecycle.isPending ? lifecycle.variables.id : null}
          onAction={onAction}
        />
        <Pager
          page={page}
          pages={Math.ceil(total / pageSize)}
          onPage={(next) => {
            update({ page: next });
          }}
        />
      </>
    );
  }

  return (
    <section className={styles.page}>
      <h1 className={styles.title}>{t('pages.library.title')}</h1>
      <p className={styles.intro}>{t('library.intro')}</p>
      <LibraryFilters filters={filters} onChange={update} />
      {lifecycle.isError && (
        <p className={styles.error} role="alert">
          {errorMessage(lifecycle.error)}
        </p>
      )}
      {body}
      {editing && (
        <EditDocumentDialog
          key={editing.id}
          document={editing}
          onClose={() => {
            setEditing(null);
          }}
        />
      )}
    </section>
  );
}
