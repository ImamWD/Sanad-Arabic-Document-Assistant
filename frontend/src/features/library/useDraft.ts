import { useEffect, useRef, useState } from 'react';

/**
 * A text field's own value for a setting that lives elsewhere (the URL). It follows the
 * setting when that changes from outside (Clear filters, the back button), and hands each edit
 * to `commit`, after `delay` ms of quiet when set.
 */
export function useDraft(value: string, commit: (draft: string) => void, delay = 0) {
  const [draft, setDraft] = useState(value);
  const [seen, setSeen] = useState(value);
  if (value !== seen) {
    setSeen(value);
    setDraft(value);
  }

  const commitRef = useRef(commit);
  useEffect(() => {
    commitRef.current = commit;
  });
  const timer = useRef<number | undefined>(undefined);
  useEffect(
    () => () => {
      window.clearTimeout(timer.current);
    },
    [],
  );

  const change = (next: string) => {
    setDraft(next);
    window.clearTimeout(timer.current);
    if (delay > 0) {
      timer.current = window.setTimeout(() => {
        commitRef.current(next);
      }, delay);
    } else {
      commitRef.current(next);
    }
  };

  return [draft, change] as const;
}
