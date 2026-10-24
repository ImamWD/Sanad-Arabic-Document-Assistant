import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Bidi } from '../../lib/BidiText';
import { useErrorMessage } from '../../lib/useErrorMessage';
import { useFormat } from '../../lib/useFormat';
import { useCurrentUser } from '../auth/session';
import { queriesQuery, storedQueryQuery } from './api';
import styles from './HistoryPanel.module.css';
import type { StoredQuery } from './types';

interface HistoryPanelProps {
  id: string;
  /** The session the history belongs to (useHistoryScope). */
  scope: number;
  onShow: (query: StoredQuery) => void;
}

/**
 * The user's own questions (GET /api/queries). Mounted only while open, so the Ask page itself
 * never fetches on arrival and a language switch never refetches (no language in any key).
 */
export function HistoryPanel({ id, scope, onShow }: HistoryPanelProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const errorMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const user = useCurrentUser();
  const queries = useQuery(queriesQuery(scope));
  const headingId = useId();
  const [selected, setSelected] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const latest = useRef<string | null>(null);

  const open = (queryId: string) => {
    latest.current = queryId;
    setSelected(queryId);
    setLoadError(null);
    queryClient.query(storedQueryQuery(scope, queryId)).then(
      (query) => {
        if (latest.current === queryId) onShow(query);
      },
      (error: unknown) => {
        if (latest.current === queryId) setLoadError(error);
      },
    );
  };

  let body;
  if (queries.isPending) {
    body = <p className={styles.message}>{t('common.loading')}</p>;
  } else if (queries.isError) {
    body = (
      <p className={styles.error} role="alert">
        {errorMessage(queries.error)}
      </p>
    );
  } else if (queries.data.length === 0) {
    body = <p className={styles.message}>{t('ask.history.empty')}</p>;
  } else {
    body = (
      <ul className={styles.list}>
        {queries.data.map((query) => (
          <li key={query.id}>
            <button
              type="button"
              className={styles.item}
              aria-current={selected === query.id ? 'true' : undefined}
              onClick={() => {
                open(query.id);
              }}
            >
              <span className={styles.question}>
                <Bidi text={query.question} />
              </span>
              <span className={styles.meta}>
                <span className={styles[query.outcome]}>{t(`ask.outcome.${query.outcome}`)}</span>
                {query.created_at && <span>{format.dateTime(query.created_at)}</span>}
              </span>
            </button>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <aside id={id} className={styles.panel} aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.heading}>
        {t('ask.history.heading')}
      </h2>
      {/* The guest is one shared account: it sees only this session's questions (R1). */}
      {user.is_guest && <p className={styles.hint}>{t('ask.history.guestHint')}</p>}
      {loadError !== null && (
        <p className={styles.error} role="alert">
          {errorMessage(loadError)}
        </p>
      )}
      {body}
    </aside>
  );
}
