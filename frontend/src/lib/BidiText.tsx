import { Fragment, useMemo } from 'react';

import { splitBidi } from './bidi';
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
 * A content block whose direction follows its own text (dir="auto" + unicode-bidi: plaintext),
 * not the UI locale, with Latin runs, codes and URLs isolated in <bdi>.
 */
export function Bidi({ text, as: Tag = 'span', className }: BidiProps) {
  const segments = useMemo(() => splitBidi(text), [text]);
  return (
    <Tag dir="auto" className={cx(styles.bidi, className)}>
      {segments.map((segment, i) =>
        segment.isolate ? (
          <bdi key={i}>{segment.text}</bdi>
        ) : (
          <Fragment key={i}>{segment.text}</Fragment>
        ),
      )}
    </Tag>
  );
}
