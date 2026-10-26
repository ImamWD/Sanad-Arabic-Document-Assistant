import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import { useFormat } from '../../lib/useFormat';
import type { Eta, Stage } from './askState';
import { ETA_NOTICE_SECONDS, OVERRUN_FACTOR } from './config';
import { useElapsedSeconds } from './useElapsedSeconds';
import styles from './WaitStatus.module.css';

/**
 * From this estimate up, or when the server capped it (R1d), the wait can't be told: the
 * screen says the server is busy, with no number and a progress bar that claims no end.
 */
export const BUSY_SECONDS = 600;

interface WaitStatusProps {
  stage: Stage;
  position: number | null;
  sources: number | null;
  eta: Eta | null;
}

/**
 * The screen never looks frozen (client requirement, SYSTEM_DESIGN §6): the stage in words,
 * the long-answer notice before the wait, then elapsed time against the estimate until the
 * first token, and "taking longer than usual" past 1.25 times the estimate. Durations read
 * in seconds below 90 and in minutes from there (format.duration).
 */
export function WaitStatus({ stage, position, sources, eta }: WaitStatusProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const elapsedId = useId();
  const waiting = eta !== null && stage !== 'writing' ? eta : null;
  const elapsed = useElapsedSeconds(waiting ? waiting.since : null);
  const busy = waiting !== null && (waiting.capped || waiting.expectedSeconds >= BUSY_SECONDS);

  let detail: string | null = null;
  if (stage === 'queued' && position !== null) {
    detail = t('ask.detail.queued', { position: format.number(position) });
  } else if (stage === 'reading' && sources !== null) {
    detail = t('ask.detail.reading', { sources: format.number(sources) });
  }
  const overrun = waiting !== null && elapsed > waiting.expectedSeconds * OVERRUN_FACTOR;

  let elapsedText: string | null = null;
  if (waiting) {
    if (overrun) elapsedText = t('ask.wait.overrun', { elapsed: format.duration(elapsed) });
    else if (busy) elapsedText = t('ask.wait.elapsedOnly', { elapsed: format.duration(elapsed) });
    else {
      elapsedText = t('ask.wait.elapsed', {
        elapsed: format.duration(elapsed),
        expected: format.duration(waiting.expectedSeconds),
      });
    }
  }

  return (
    <div className={styles.wait}>
      <div role="status" className={styles.status}>
        <p className={styles.stage}>
          <span className={styles.pulse} aria-hidden="true" />
          <span>{t(`ask.stage.${stage}`)}</span>
          {detail && <span className={styles.detail}>{detail}</span>}
        </p>
        {waiting && waiting.expectedSeconds > ETA_NOTICE_SECONDS && (
          <p className={styles.notice}>
            {busy
              ? t('ask.wait.busy')
              : t('ask.wait.notice', { duration: format.duration(waiting.expectedSeconds) })}
          </p>
        )}
      </div>
      {waiting && (
        <div className={styles.elapsed}>
          {overrun || busy ? (
            // No max or value: an indeterminate bar, which promises no end.
            <progress className={styles.progress} aria-labelledby={elapsedId} />
          ) : (
            <progress
              className={styles.progress}
              max={waiting.expectedSeconds}
              value={Math.min(elapsed, waiting.expectedSeconds)}
              aria-labelledby={elapsedId}
            />
          )}
          <p id={elapsedId} className={overrun ? styles.overrun : styles.elapsedText}>
            {elapsedText}
          </p>
        </div>
      )}
    </div>
  );
}
