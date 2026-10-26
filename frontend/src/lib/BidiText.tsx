import { Fragment, useMemo } from 'react';

import { baseDirection, isUrl, splitBidi } from './bidi';
import styles from './BidiText.module.css';
import { cx } from './cx';

type BidiTag = 'span' | 'p' | 'div' | 'li' | 'td' | 'th' | 'h1' | 'h2' | 'h3' | 'blockquote';

interface BidiProps {
  /** Content in any language: an answer, snippet, title or filename. Rendered as text only. */
  text: string;
  as?: BidiTag;
  className?: string | undefined;
}

/**
 * One isolated Latin run, kept readable when its line wraps. A line break inside a code
 * ("WASH-|2018-01") splits it across lines and, in right-to-left text, swaps its halves, so:
 * a code or a word never breaks inside, a URL breaks only after a slash, and the words of a
 * phrase break only at their spaces.
 */
function Isolate({ text }: { text: string }) {
  if (isUrl(text)) {
    const parts = text.split(/(?<=\/)/);
    return (
      <bdi>
        {parts.map((part, i) => (
          <Fragment key={i}>
            {i > 0 && <wbr />}
            <span className={styles.nowrap}>{part}</span>
          </Fragment>
        ))}
      </bdi>
    );
  }
  if (!/\s/.test(text)) return <bdi className={styles.nowrap}>{text}</bdi>;
  return (
    <bdi>
      {text.split(/(\s+)/).map((word, i) =>
        /\s/.test(word) ? (
          <Fragment key={i}>{word}</Fragment>
        ) : (
          <span key={i} className={styles.nowrap}>
            {word}
          </span>
        ),
      )}
    </bdi>
  );
}

/**
 * A content block whose direction follows its own text, not the UI locale, with Latin runs,
 * codes and URLs isolated in <bdi>. The direction is set from the text's first strong
 * character (baseDirection); only text with no letters at all is left to dir="auto".
 */
export function Bidi({ text, as: Tag = 'span', className }: BidiProps) {
  const segments = useMemo(() => splitBidi(text), [text]);
  const dir = useMemo(() => baseDirection(text), [text]);
  return (
    <Tag dir={dir ?? 'auto'} className={cx(styles.bidi, dir && styles.known, className)}>
      {segments.map((segment, i) =>
        segment.isolate ? (
          <Isolate key={i} text={segment.text} />
        ) : (
          <Fragment key={i}>{segment.text}</Fragment>
        ),
      )}
    </Tag>
  );
}
