import { type SubmitEvent, useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useErrorMessage } from '../../lib/useErrorMessage';
import type { Role } from '../auth/types';
import { useUpdateUser } from './api';
import { type AdminUser, LANGUAGES, ROLES, type UserChanges } from './types';
import styles from './UserForm.module.css';

interface EditUserFormProps {
  id: string;
  user: AdminUser;
  /** The signed-in admin's own row: they can't change their role or deactivate themselves. */
  isSelf: boolean;
  /** `saved` is false after Cancel, or a Save with nothing changed. */
  onClose: (saved: boolean) => void;
}

/**
 * Role, language and active for one account. The server refuses what the guardrails below
 * prevent (CANNOT_CHANGE_OWN_ACCESS, GUEST_ROLE_FIXED); the form never sends those changes.
 * Deactivating anyone needs a second, explicit confirmation.
 */
export function EditUserForm({ id, user, isSelf, onClose }: EditUserFormProps) {
  const { t } = useTranslation();
  const errorMessage = useErrorMessage();
  const update = useUpdateUser();
  const [role, setRole] = useState<Role>(user.role);
  const [language, setLanguage] = useState(user.preferred_language);
  const [active, setActive] = useState(user.is_active);
  const [confirming, setConfirming] = useState(false);
  const firstControl = useRef<HTMLSelectElement>(null);
  const goBack = useRef<HTMLButtonElement>(null);
  const ids = {
    role: useId(),
    language: useId(),
    active: useId(),
    hint: useId(),
    error: useId(),
    confirmTitle: useId(),
    confirmBody: useId(),
  };

  // The guest is always a viewer, and an admin never changes their own access.
  const roleFixed = user.is_guest || isSelf;
  const changes: UserChanges = {};
  if (!roleFixed && role !== user.role) changes.role = role;
  if (language !== user.preferred_language) changes.preferred_language = language;
  if (!isSelf && active !== user.is_active) changes.is_active = active;

  useEffect(() => {
    firstControl.current?.focus();
  }, []);

  useEffect(() => {
    if (confirming) goBack.current?.focus();
  }, [confirming]);

  const save = () => {
    if (Object.keys(changes).length === 0) {
      onClose(false);
      return;
    }
    update.mutate(
      { id: user.id, changes },
      {
        onSuccess: () => {
          onClose(true);
        },
        onError: () => {
          setConfirming(false);
        },
      },
    );
  };

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    update.reset();
    if (changes.is_active === false) setConfirming(true);
    else save();
  };

  const hint = isSelf ? t('admin.edit.selfHint') : user.is_guest ? t('admin.edit.guestHint') : null;
  const locked = confirming || update.isPending;

  return (
    <form
      id={id}
      className={styles.inline}
      aria-label={t('admin.edit.label', { name: user.name })}
      onSubmit={onSubmit}
    >
      <fieldset className={styles.fieldset} disabled={locked}>
        <div className={styles.fields}>
          <div className={styles.field}>
            {user.is_guest ? (
              // Not a control at all: the guest's role is fixed by the server.
              <>
                <span className={styles.label}>{t('admin.fields.role')}</span>
                <p className={styles.fixed}>
                  {t(`roles.${user.role}`)}
                  <span className={styles.badge}>{t('admin.users.roleFixed')}</span>
                </p>
              </>
            ) : (
              <>
                <label className={styles.label} htmlFor={ids.role}>
                  {t('admin.fields.role')}
                </label>
                <select
                  ref={isSelf ? undefined : firstControl}
                  id={ids.role}
                  className={styles.input}
                  value={role}
                  disabled={isSelf}
                  aria-describedby={isSelf ? ids.hint : undefined}
                  onChange={(event) => {
                    setRole(ROLES.find((each) => each === event.target.value) ?? user.role);
                  }}
                >
                  {ROLES.map((each) => (
                    <option key={each} value={each}>
                      {t(`roles.${each}`)}
                    </option>
                  ))}
                </select>
              </>
            )}
          </div>
          <div className={styles.field}>
            <label className={styles.label} htmlFor={ids.language}>
              {t('admin.fields.language')}
            </label>
            <select
              ref={roleFixed ? firstControl : undefined}
              id={ids.language}
              className={styles.input}
              value={language}
              onChange={(event) => {
                setLanguage(LANGUAGES.find((each) => each === event.target.value) ?? language);
              }}
            >
              {LANGUAGES.map((each) => (
                <option key={each} value={each}>
                  {t(`admin.languages.${each}`)}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.check}>
            <input
              id={ids.active}
              type="checkbox"
              checked={active}
              disabled={isSelf}
              aria-describedby={isSelf ? ids.hint : undefined}
              onChange={(event) => {
                setActive(event.target.checked);
              }}
            />
            <label htmlFor={ids.active}>{t('admin.fields.active')}</label>
          </div>
        </div>
        {hint && (
          <p id={ids.hint} className={styles.hint}>
            {hint}
          </p>
        )}
      </fieldset>
      {update.error !== null && (
        <p id={ids.error} className={styles.error} role="alert">
          {errorMessage(update.error)}
        </p>
      )}
      {confirming ? (
        <div
          className={styles.confirm}
          role="alertdialog"
          aria-labelledby={ids.confirmTitle}
          aria-describedby={ids.confirmBody}
        >
          <p id={ids.confirmTitle} className={styles.confirmTitle}>
            {t('admin.edit.confirmTitle')}
          </p>
          <p id={ids.confirmBody} className={styles.confirmBody}>
            {t('admin.edit.confirmBody')}
          </p>
          <div className={styles.actions}>
            <button
              className={styles.danger}
              type="button"
              disabled={update.isPending}
              onClick={save}
            >
              {update.isPending ? t('admin.edit.saving') : t('admin.edit.confirm')}
            </button>
            <button
              ref={goBack}
              className={styles.secondary}
              type="button"
              disabled={update.isPending}
              onClick={() => {
                setConfirming(false);
              }}
            >
              {t('admin.edit.back')}
            </button>
          </div>
        </div>
      ) : (
        <div className={styles.actions}>
          <button className={styles.primary} type="submit" disabled={update.isPending}>
            {update.isPending ? t('admin.edit.saving') : t('admin.edit.save')}
          </button>
          <button
            className={styles.secondary}
            type="button"
            disabled={update.isPending}
            onClick={() => {
              onClose(false);
            }}
          >
            {t('admin.edit.cancel')}
          </button>
        </div>
      )}
    </form>
  );
}
