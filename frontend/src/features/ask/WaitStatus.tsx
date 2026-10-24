import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import { useFormat } from '../../lib/useFormat';
import type { Eta, Stage } from './askState';
import { ETA_NOTICE_SECONDS, OVERRUN_FACTOR } from './config';
import { useElapsedSeconds } from './useElapsedSeconds';
import styles from './WaitStatus.module.css';

interface WaitStatusProps {
  stage: Stage;
  position: number | null;
  sources: number | null;
  eta: Eta | null;
}

/**
 * The screen never looks frozen (client requirement, SYSTEM_DESIGN §6): the stage in words,
 * the long-answer notice before the wait, then elapsed time against the estimate until the
 * first token, and "taking longer than usual" past 1.25 times the estimate.
 */
export function WaitStatus({ stage, position, sources, eta }: WaitStatusProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const elapsedId = useId();
  const waiting = eta !== null && stage !== 'writing' ? eta : null;
  const elapsed = useElapsedSeconds(waiting ? waiting.since : null);

  // Intl picks the right plural for the unit in each language ("21 ثانية", "3 ثوانٍ").
  const seconds = (value: number) =>
    format.number(Math.round(value), { style: 'unit', unit: 'second', unitDisplay: 'long' });

  let detail: string | null = null;
  if (stage === 'queued' && position !== null) {
    detail = t('ask.detail.queued', { position: format.number(position) });
  } else if (stage === 'reading' && sources !== null) {
    detail = t('ask.detail.reading', { sources: format.number(sources) });
  }
  const overrun = waiting !== null && elapsed > waiting.expectedSeconds * OVERRUN_FACTOR;

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
            {t('ask.wait.notice', { duration: seconds(waiting.expectedSeconds) })}
          </p>
        )}
      </div>
      {waiting && (
        <div className={styles.elapsed}>
          {overrun ? (
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
            {overrun
              ? t('ask.wait.overrun', { elapsed: seconds(elapsed) })
              : t('ask.wait.elapsed', {
                  elapsed: seconds(elapsed),
                  expected: seconds(waiting.expectedSeconds),
                })}
          </p>
        </div>
      )}
    </div>
  );
}
