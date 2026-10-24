import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { UNKNOWN_ERROR } from '../../lib/api';
import { Bidi } from '../../lib/BidiText';
import { cx } from '../../lib/cx';
import { isTranslatedErrorCode } from '../../lib/errors';
import { useFormat } from '../../lib/useFormat';
import { AnswerText, AnswerView, LowConfidenceBanner } from './AnswerView';
import styles from './AskPage.module.css';
import type { AskState, ErrorInfo } from './askState';
import { HistoryPanel } from './HistoryPanel';
import { QuestionForm } from './QuestionForm';
import { useAsk } from './useAsk';
import { useHistoryScope } from './useHistoryScope';
import { WaitStatus } from './WaitStatus';

function Failure({ error, onRetry }: { error: ErrorInfo; onRetry: () => void }) {
  const { t } = useTranslation();
  const code = isTranslatedErrorCode(error.code) ? error.code : UNKNOWN_ERROR;
  return (
    <div className={styles.failure}>
      <p className={styles.error} role="alert">
        {t(`errors.${code}`, error.params)}
      </p>
      <button type="button" className={styles.retry} onClick={onRetry}>
        {t('ask.retry')}
      </button>
    </div>
  );
}

function AskResult({ state, onRetry }: { state: AskState; onRetry: (question: string) => void }) {
  const { t } = useTranslation();
  const format = useFormat();
  if (state.phase === 'idle') return null;
  return (
    <article className={styles.result}>
      <Bidi as="h2" className={styles.question} text={state.question} />
      {state.phase === 'done' && state.askedAt && (
        <p className={styles.askedAt}>
          {t('ask.history.askedAt', { time: format.dateTime(state.askedAt) })}
        </p>
      )}
      {state.phase === 'streaming' && (
        <>
          {/* The amber banner from the reading stage on, before the first word (D4). */}
          {state.band === 'low_confidence' && <LowConfidenceBanner />}
          <WaitStatus
            stage={state.stage}
            position={state.position}
            sources={state.sources}
            eta={state.eta}
          />
          {state.text && <AnswerText text={state.text} streaming />}
        </>
      )}
      {state.phase === 'done' && <AnswerView result={state.result} />}
      {state.phase === 'failed' && (
        <Failure
          error={state.error}
          onRetry={() => {
            onRetry(state.question);
          }}
        />
      )}
    </article>
  );
}

/** /ask, the landing page after sign-in (the guest's too). */
export function AskPage() {
  const { t } = useTranslation();
  const historyScope = useHistoryScope();
  const { state, ask, show } = useAsk(historyScope);
  const [historyOpen, setHistoryOpen] = useState(false);
  const historyId = useId();

  return (
    <div className={cx(styles.layout, historyOpen && styles.withHistory)}>
      <section className={styles.main}>
        <header className={styles.header}>
          <h1 className={styles.title}>{t('pages.ask.title')}</h1>
          {/* Everyone has a history, the guest too: for the shared guest account the server
              returns only the current session's questions (ROADMAP R1). */}
          <button
            type="button"
            className={styles.historyToggle}
            aria-expanded={historyOpen}
            aria-controls={historyOpen ? historyId : undefined}
            onClick={() => {
              setHistoryOpen((open) => !open);
            }}
          >
            {t('ask.history.toggle')}
          </button>
        </header>
        <QuestionForm busy={state.phase === 'streaming'} onAsk={ask} />
        <AskResult state={state} onRetry={ask} />
      </section>
      {historyOpen && <HistoryPanel id={historyId} scope={historyScope} onShow={show} />}
    </div>
  );
}
