import { type SubmitEvent, useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { currentLanguage } from '../../app/i18n';
import { cx } from '../../lib/cx';
import { useErrorMessage } from '../../lib/useErrorMessage';
import { invalidFields, useCreateUser } from './api';
import { LANGUAGES, type NewUser, ROLES } from './types';
import styles from './UserForm.module.css';

interface CreateUserFormProps {
  id: string;
  onCancel: () => void;
  onCreated: () => void;
}

type TextField = 'name' | 'email' | 'password';

const TEXT_FIELDS: readonly { field: TextField; type: string; autoComplete: string }[] = [
  { field: 'name', type: 'text', autoComplete: 'off' },
  { field: 'email', type: 'email', autoComplete: 'off' },
  { field: 'password', type: 'password', autoComplete: 'new-password' },
];

/**
 * A new account: name, email, password, role and language. The password rules (minimum
 * length) are the server's, so a short password comes back as PASSWORD_TOO_SHORT.
 */
export function CreateUserForm({ id, onCancel, onCreated }: CreateUserFormProps) {
  const { t, i18n } = useTranslation();
  const errorMessage = useErrorMessage();
  const create = useCreateUser();
  // Controlled, so a language switch (or a failed request) keeps everything typed so far.
  const [user, setUser] = useState<NewUser>(() => ({
    name: '',
    email: '',
    password: '',
    role: 'viewer',
    preferred_language: currentLanguage(i18n),
  }));
  const [missing, setMissing] = useState(false);
  const nameInput = useRef<HTMLInputElement>(null);
  const ids = {
    title: useId(),
    name: useId(),
    email: useId(),
    password: useId(),
    role: useId(),
    language: useId(),
    error: useId(),
  };

  useEffect(() => {
    nameInput.current?.focus();
  }, []);

  const set = <K extends keyof NewUser>(field: K, value: NewUser[K]) => {
    setUser((current) => ({ ...current, [field]: value }));
  };

  const blamed = invalidFields(create.error);
  const isEmpty = (field: TextField) => user[field].trim() === '';
  const invalid = (field: TextField) => (missing && isEmpty(field)) || blamed.has(field);
  const message = missing
    ? t('admin.create.missingFields')
    : create.error
      ? errorMessage(create.error)
      : '';

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const body: NewUser = { ...user, name: user.name.trim(), email: user.email.trim() };
    const incomplete = !body.name || !body.email || !body.password;
    setMissing(incomplete);
    create.reset();
    if (incomplete) return;
    create.mutate(body, { onSuccess: onCreated });
  };

  const textInputs = TEXT_FIELDS.map(({ field, type, autoComplete }) => (
    <div key={field} className={styles.field}>
      <label className={styles.label} htmlFor={ids[field]}>
        {t(`admin.fields.${field}`)}
      </label>
      <input
        ref={field === 'name' ? nameInput : undefined}
        id={ids[field]}
        className={cx(styles.input, invalid(field) && styles.invalid)}
        type={type}
        dir={field === 'password' ? undefined : 'auto'}
        autoComplete={autoComplete}
        value={user[field]}
        aria-invalid={invalid(field) || undefined}
        aria-describedby={message ? ids.error : undefined}
        onChange={(event) => {
          set(field, event.target.value);
        }}
      />
    </div>
  ));

  return (
    // noValidate: the browser's own validation bubbles speak the browser's language.
    <form
      id={id}
      className={styles.panel}
      aria-labelledby={ids.title}
      onSubmit={onSubmit}
      noValidate
    >
      <h2 id={ids.title} className={styles.title}>
        {t('admin.create.heading')}
      </h2>
      <div className={styles.fields}>
        {textInputs}
        <div className={styles.field}>
          <label className={styles.label} htmlFor={ids.role}>
            {t('admin.fields.role')}
          </label>
          <select
            id={ids.role}
            className={styles.input}
            value={user.role}
            onChange={(event) => {
              set('role', ROLES.find((role) => role === event.target.value) ?? 'viewer');
            }}
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {t(`roles.${role}`)}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={ids.language}>
            {t('admin.fields.language')}
          </label>
          <select
            id={ids.language}
            className={styles.input}
            value={user.preferred_language}
            onChange={(event) => {
              const language = LANGUAGES.find((lang) => lang === event.target.value);
              if (language) set('preferred_language', language);
            }}
          >
            {LANGUAGES.map((lang) => (
              <option key={lang} value={lang}>
                {t(`admin.languages.${lang}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {message && (
        <p id={ids.error} className={styles.error} role="alert">
          {message}
        </p>
      )}
      <div className={styles.actions}>
        <button className={styles.primary} type="submit" disabled={create.isPending}>
          {create.isPending ? t('admin.create.submitting') : t('admin.create.submit')}
        </button>
        <button className={styles.secondary} type="button" onClick={onCancel}>
          {t('admin.create.cancel')}
        </button>
      </div>
    </form>
  );
}
