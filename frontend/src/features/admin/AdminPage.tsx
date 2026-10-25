import { useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import styles from './AdminPage.module.css';
import { CreateUserForm } from './CreateUserForm';
import { UsersTable } from './UsersTable';

type Notice = 'created' | 'saved';

/**
 * /admin (admins only): the user list, plus create and edit (role, active, language).
 * Accounts are never deleted, only deactivated, matching the API. The usage log is v2.
 */
export function AdminPage() {
  const { t } = useTranslation();
  const [creating, setCreating] = useState(false);
  // A key, not text, so the status line follows a language switch.
  const [notice, setNotice] = useState<Notice | null>(null);
  const addButton = useRef<HTMLButtonElement>(null);
  const restoreFocus = useRef(false);
  const createId = useId();

  // After the create form closes, focus goes back to the button that opened it.
  useEffect(() => {
    if (creating || !restoreFocus.current) return;
    restoreFocus.current = false;
    addButton.current?.focus();
  }, [creating]);

  const closeCreate = (created: boolean) => {
    restoreFocus.current = true;
    setCreating(false);
    if (created) setNotice('created');
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>{t('pages.admin.title')}</h1>
          <p className={styles.intro}>{t('admin.intro')}</p>
        </div>
        <button
          ref={addButton}
          type="button"
          className={styles.add}
          aria-expanded={creating}
          aria-controls={creating ? createId : undefined}
          onClick={() => {
            if (creating) {
              closeCreate(false);
            } else {
              setNotice(null);
              setCreating(true);
            }
          }}
        >
          {t('admin.create.open')}
        </button>
      </header>
      {/* Always rendered, so screen readers announce what appears in it. */}
      <p className={styles.notice} role="status">
        {notice && t(`admin.notice.${notice}`)}
      </p>
      {creating && (
        <CreateUserForm
          id={createId}
          onCancel={() => {
            closeCreate(false);
          }}
          onCreated={() => {
            closeCreate(true);
          }}
        />
      )}
      <UsersTable
        onEdit={() => {
          setNotice(null);
        }}
        onSaved={() => {
          setNotice('saved');
        }}
      />
    </div>
  );
}
