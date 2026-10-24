import { useQuery } from '@tanstack/react-query';
import { Fragment, useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Bidi } from '../../lib/BidiText';
import { cx } from '../../lib/cx';
import { useErrorMessage } from '../../lib/useErrorMessage';
import { useFormat } from '../../lib/useFormat';
import { useCurrentUser } from '../auth/session';
import { adminUsersQuery } from './api';
import { EditUserForm } from './EditUserForm';
import styles from './UsersTable.module.css';

const COLUMNS = 8;

interface UsersTableProps {
  /** Called after an edit is saved, for the page's status line. */
  onSaved: () => void;
  /** Called when an edit form opens, so the page can clear an old status. */
  onEdit: () => void;
}

/** Every account, oldest first (GET /api/admin/users), each with an inline edit form. */
export function UsersTable({ onSaved, onEdit }: UsersTableProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const errorMessage = useErrorMessage();
  const me = useCurrentUser();
  const users = useQuery(adminUsersQuery);
  const [editing, setEditing] = useState<string | null>(null);
  const headingId = useId();
  const idPrefix = useId();
  const returnFocusTo = useRef<string | null>(null);

  const editButtonId = (userId: string) => `${idPrefix}-edit-${userId}`;
  const formId = (userId: string) => `${idPrefix}-form-${userId}`;

  // After an edit form closes, focus goes back to the row's Edit button.
  useEffect(() => {
    if (editing !== null || returnFocusTo.current === null) return;
    document.getElementById(editButtonId(returnFocusTo.current))?.focus();
    returnFocusTo.current = null;
  });

  const close = (userId: string, saved: boolean) => {
    returnFocusTo.current = userId;
    setEditing(null);
    if (saved) onSaved();
  };

  let body;
  if (users.isPending) {
    body = <p className={styles.message}>{t('common.loading')}</p>;
  } else if (users.isError) {
    body = (
      <div className={styles.failure}>
        <p className={styles.error} role="alert">
          {errorMessage(users.error)}
        </p>
        <button
          type="button"
          className={styles.button}
          onClick={() => {
            void users.refetch();
          }}
        >
          {t('admin.retry')}
        </button>
      </div>
    );
  } else {
    body = (
      // A wide table scrolls inside its own box on narrow screens, not the whole page.
      <div className={styles.scroll} role="region" aria-labelledby={headingId} tabIndex={0}>
        <table className={styles.table} aria-labelledby={headingId}>
          <thead>
            <tr>
              <th scope="col">{t('admin.fields.name')}</th>
              <th scope="col">{t('admin.fields.email')}</th>
              <th scope="col">{t('admin.fields.role')}</th>
              <th scope="col">{t('admin.fields.language')}</th>
              <th scope="col">{t('admin.users.status')}</th>
              <th scope="col">{t('admin.users.created')}</th>
              <th scope="col">{t('admin.users.lastLogin')}</th>
              <th scope="col">{t('admin.users.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {users.data.map((user) => {
              const isSelf = user.id === me.id;
              const open = editing === user.id;
              return (
                <Fragment key={user.id}>
                  <tr className={cx(!user.is_active && styles.inactiveRow)}>
                    <th scope="row" className={styles.nameCell}>
                      <Bidi text={user.name} />
                      {isSelf && <span className={styles.badge}>{t('admin.users.you')}</span>}
                      {user.is_guest && (
                        <span className={cx(styles.badge, styles.guest)}>{t('roles.guest')}</span>
                      )}
                    </th>
                    <td>
                      <Bidi className={styles.email} text={user.email} />
                    </td>
                    <td>
                      {t(`roles.${user.role}`)}
                      {user.is_guest && (
                        <span className={styles.badge}>{t('admin.users.roleFixed')}</span>
                      )}
                    </td>
                    <td>{t(`admin.languages.${user.preferred_language}`)}</td>
                    <td>
                      <span className={user.is_active ? styles.active : styles.inactive}>
                        {user.is_active ? t('admin.users.active') : t('admin.users.inactive')}
                      </span>
                    </td>
                    <td>{format.date(user.created_at)}</td>
                    <td>
                      {user.last_login_at
                        ? format.dateTime(user.last_login_at)
                        : t('admin.users.never')}
                    </td>
                    <td>
                      <button
                        id={editButtonId(user.id)}
                        type="button"
                        className={styles.button}
                        aria-label={t('admin.users.editUser', { name: user.name })}
                        aria-expanded={open}
                        aria-controls={open ? formId(user.id) : undefined}
                        onClick={() => {
                          if (open) {
                            close(user.id, false);
                          } else {
                            setEditing(user.id);
                            onEdit();
                          }
                        }}
                      >
                        {t('admin.users.edit')}
                      </button>
                    </td>
                  </tr>
                  {open && (
                    <tr className={styles.editRow}>
                      <td colSpan={COLUMNS}>
                        <EditUserForm
                          id={formId(user.id)}
                          user={user}
                          isSelf={isSelf}
                          onClose={(saved) => {
                            close(user.id, saved);
                          }}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <section className={styles.section}>
      <h2 id={headingId} className={styles.heading}>
        {t('admin.users.heading')}
      </h2>
      {body}
    </section>
  );
}
