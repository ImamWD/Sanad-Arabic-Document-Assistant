import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { Bidi } from '../../lib/BidiText';
import { cx } from '../../lib/cx';
import { useFormat } from '../../lib/useFormat';
import styles from './AnswerView.module.css';
import { MAX_NEAREST_DOCUMENTS } from './config';
import type { AnswerResult, Citation, NearestDocument } from './types';

const documentPath = (id: string) => `/documents/${encodeURIComponent(id)}`;

/** The amber low-confidence banner with the approved D4 copy. */
export function LowConfidenceBanner() {
  const { t } = useTranslation();
  return (
    <p className={styles.banner} role="note">
      {t('answer.lowConfidence')}
    </p>
  );
}

/** Answer text, one bidi-isolated paragraph per line, so each takes its own direction. */
export function AnswerText({ text, streaming = false }: { text: string; streaming?: boolean }) {
  const paragraphs = text.split(/\n+/).filter((line) => line.trim());
  return (
    <div className={cx(styles.answer, streaming && styles.streaming)} aria-busy={streaming}>
      {paragraphs.map((paragraph, i) => (
        <Bidi key={i} as="p" className={styles.paragraph} text={paragraph} />
      ))}
    </div>
  );
}

function Refusal({ result }: { result: AnswerResult }) {
  const { t } = useTranslation();
  const nearest = result.nearest_documents.slice(0, MAX_NEAREST_DOCUMENTS);
  // "The documents don't cover this" (retrieval) versus "nothing usable in what was read"
  // (the model): the split tells honesty apart from a retrieval problem (D4).
  const reason =
    result.refusal_reason === 'gate'
      ? t('ask.refusal.gate')
      : result.refusal_reason
        ? t('ask.refusal.read')
        : null;
  return (
    <div className={styles.refusal} data-refusal-reason={result.refusal_reason ?? undefined}>
      <p className={styles.refusalTitle}>{t('answer.refusal')}</p>
      {reason && <p className={styles.refusalReason}>{reason}</p>}
      {nearest.length > 0 && <NearestDocuments documents={nearest} />}
    </div>
  );
}

function NearestDocuments({ documents }: { documents: NearestDocument[] }) {
  const { t } = useTranslation();
  const headingId = useId();
  return (
    <div className={styles.nearest}>
      <p id={headingId} className={styles.nearestHeading}>
        {t('ask.refusal.nearest')}
      </p>
      <ul className={styles.nearestList} aria-labelledby={headingId}>
        {documents.map((doc) => (
          <li key={doc.document_id}>
            <Link className={styles.nearestLink} to={documentPath(doc.document_id)}>
              <Bidi text={doc.title} />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CitationCard({ citation }: { citation: Citation }) {
  const { t } = useTranslation();
  const format = useFormat();
  const to = `${documentPath(citation.document_id)}?page=${String(citation.page_number)}`;
  return (
    <li>
      <Link className={styles.card} to={to}>
        <span className={styles.cardHead}>
          <span className={styles.rank}>{format.number(citation.rank)}</span>
          {/* The block follows the page's direction, so the title lines up with the UI; the
              inline <Bidi> inside keeps the title's own reading order. */}
          <span className={styles.cardTitle}>
            <Bidi text={citation.title} />
          </span>
          <span className={styles.page}>
            {t('ask.citations.page', { page: format.number(citation.page_number) })}
          </span>
        </span>
        {citation.snippet && <Bidi as="p" className={styles.snippet} text={citation.snippet} />}
        {citation.is_converted && (
          <span className={styles.converted}>
            {citation.file_type === 'docx'
              ? t('ask.citations.convertedWord')
              : t('ask.citations.convertedOther')}
          </span>
        )}
      </Link>
    </li>
  );
}

/** A validated answer: the refusal, or the answer with its banner and citation cards. */
export function AnswerView({ result }: { result: AnswerResult }) {
  const { t } = useTranslation();
  const headingId = useId();
  if (result.outcome === 'no_answer' || result.answer === null) {
    return <Refusal result={result} />;
  }
  const lowConfidence = result.outcome === 'low_confidence' || result.band === 'low_confidence';
  return (
    <>
      {lowConfidence && <LowConfidenceBanner />}
      <AnswerText text={result.answer} />
      <section className={styles.citations} aria-labelledby={headingId}>
        <h3 id={headingId} className={styles.citationsHeading}>
          {t('ask.citations.heading')}
        </h3>
        <ol className={styles.cardList}>
          {result.citations.map((citation) => (
            <CitationCard key={citation.rank} citation={citation} />
          ))}
        </ol>
      </section>
    </>
  );
}
