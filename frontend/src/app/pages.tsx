// Placeholder screens. F2–F5 replace each route's element in routes.tsx with their feature.
import { useTranslation } from 'react-i18next';
import { Link, useParams, useSearchParams } from 'react-router';

import { Bidi } from '../lib/BidiText';
import { useFormat } from '../lib/useFormat';
import styles from './pages.module.css';

type PlaceholderId = 'ask' | 'library' | 'upload' | 'admin';

export function PlaceholderPage({ id }: { id: PlaceholderId }) {
  const { t } = useTranslation();
  return (
    <section className={styles.page}>
      <h1 className={styles.title}>{t(`pages.${id}.title`)}</h1>
      <p className={styles.body}>{t(`pages.${id}.body`)}</p>
    </section>
  );
}

/** /documents/:id?page=N, which the viewer (F4) opens at page N. */
export function DocumentPage() {
  const { t } = useTranslation();
  const format = useFormat();
  const { id = '' } = useParams();
  const [params] = useSearchParams();
  const page = Number(params.get('page'));

  return (
    <section className={styles.page}>
      <h1 className={styles.title}>{t('pages.document.title')}</h1>
      <Bidi as="p" className={styles.meta} text={id} />
      {Number.isInteger(page) && page > 0 && (
        <p className={styles.meta}>{t('pages.document.page', { page: format.number(page) })}</p>
      )}
      <p className={styles.body}>{t('pages.document.body')}</p>
    </section>
  );
}

function StatusPage({ id }: { id: 'notFound' | 'forbidden' }) {
  const { t } = useTranslation();
  return (
    <section className={styles.page}>
      <h1 className={styles.title}>{t(`pages.${id}.title`)}</h1>
      <p className={styles.body}>{t(`pages.${id}.body`)}</p>
      <Link className={styles.link} to="/ask">
        {t('pages.backToAsk')}
      </Link>
    </section>
  );
}

export function NotFoundPage() {
  return <StatusPage id="notFound" />;
}

export function ForbiddenPage() {
  return <StatusPage id="forbidden" />;
}
