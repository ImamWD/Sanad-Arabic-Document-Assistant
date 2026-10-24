import { useTranslation } from 'react-i18next';

import { cx } from '../../lib/cx';
import { useFailureReason } from './labels';
import styles from './StatusBadge.module.css';
import type { DocumentItem, DocStatus } from './types';

/** The processing stage as a badge (SYSTEM_DESIGN §5.1). */
export function StatusBadge({ status }: { status: DocStatus }) {
  const { t } = useTranslation();
  return (
    <span className={cx(styles.badge, styles[status])} data-status={status}>
      {t(`documents.status.${status}`)}
    </span>
  );
}

/** The badge, plus the translated reason when the document failed. */
export function DocumentStatus({
  document,
}: {
  document: Pick<DocumentItem, 'status' | 'error_code' | 'error_params'>;
}) {
  const failureReason = useFailureReason();
  return (
    <span className={styles.status}>
      <StatusBadge status={document.status} />
      {document.status === 'failed' && (
        <span className={styles.reason} data-error-code={document.error_code ?? undefined}>
          {failureReason(document)}
        </span>
      )}
    </span>
  );
}

/** "Restricted": shown to editors and admins only (viewers never receive such documents). */
export function RestrictedBadge() {
  const { t } = useTranslation();
  return (
    <span className={cx(styles.badge, styles.restricted)} title={t('documents.restrictedHint')}>
      {t('documents.restricted')}
    </span>
  );
}

export function ArchivedBadge() {
  const { t } = useTranslation();
  return <span className={cx(styles.badge, styles.archived)}>{t('documents.archived')}</span>;
}

/** A missing category is flagged for review rather than given an invented one (client Q5). */
export function UncategorisedFlag() {
  const { t } = useTranslation();
  return (
    <span className={cx(styles.badge, styles.flag)} data-uncategorised="">
      {t('documents.category.none')}
    </span>
  );
}
