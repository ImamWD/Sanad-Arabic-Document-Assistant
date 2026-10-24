import { type KeyboardEvent, type SubmitEvent, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import styles from './QuestionForm.module.css';

interface QuestionFormProps {
  /** An answer is streaming: typing is allowed, sending waits until it ends. */
  busy: boolean;
  onAsk: (question: string) => void;
}

/** The question box: Enter sends, Shift+Enter starts a new line. */
export function QuestionForm({ busy, onAsk }: QuestionFormProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState('');
  const ids = { input: useId(), hint: useId() };
  const question = draft.trim();

  const send = () => {
    if (!question || busy) return;
    onAsk(question);
    setDraft('');
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // While an input method is composing (Arabic and other IMEs), Enter confirms the text.
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    send();
  };

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    send();
  };

  return (
    <form className={styles.form} onSubmit={onSubmit}>
      <label className={styles.label} htmlFor={ids.input}>
        {t('ask.form.label')}
      </label>
      <textarea
        id={ids.input}
        className={styles.input}
        name="question"
        dir="auto"
        rows={3}
        value={draft}
        placeholder={t('ask.form.placeholder')}
        aria-describedby={ids.hint}
        onChange={(event) => {
          setDraft(event.target.value);
        }}
        onKeyDown={onKeyDown}
        autoFocus
      />
      <div className={styles.row}>
        <p id={ids.hint} className={styles.hint}>
          {t('ask.form.hint')}
        </p>
        <button className={styles.submit} type="submit" disabled={busy || !question}>
          {busy ? t('ask.form.submitting') : t('ask.form.submit')}
        </button>
      </div>
    </form>
  );
}
