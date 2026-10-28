import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { useTranslation } from 'react-i18next';

import { useCurrentUser, useLogout } from '../features/auth/session';
import { Bidi } from '../lib/BidiText';
import { Icon } from '../lib/Icon';
import styles from './UserMenu.module.css';

export function UserMenu() {
  const { t } = useTranslation();
  const user = useCurrentUser();
  const logout = useLogout();
  const role = t(`roles.${user.role}`);

  // Clearing the session is enough: <RequireAuth> then sends the browser to /login.
  const signOut = () => {
    logout.mutate();
  };

  return (
    // modal={false}: the modal variant locks scrolling by injecting a <style> element, which
    // the Content-Security-Policy (style-src 'self') blocks.
    <DropdownMenu.Root modal={false}>
      <DropdownMenu.Trigger className={styles.trigger}>
        <Icon name="user" />
        {/* The guest is one shared account: it is called by its role, in the UI language,
            not by the server's account name. Real users keep their own name. */}
        {user.is_guest ? (
          <span className={styles.name}>{t('roles.guest')}</span>
        ) : (
          <Bidi className={styles.name} text={user.name} />
        )}
        <Icon name="chevronDown" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className={styles.content} align="end" sideOffset={6}>
          <DropdownMenu.Label className={styles.label}>
            {user.is_guest ? (
              <div className={styles.labelName}>{t('roles.guest')}</div>
            ) : (
              <>
                <Bidi as="div" className={styles.labelName} text={user.name} />
                <Bidi as="div" className={styles.labelMeta} text={user.email} />
                <div className={styles.labelMeta}>{role}</div>
              </>
            )}
          </DropdownMenu.Label>
          <DropdownMenu.Separator className={styles.separator} />
          <DropdownMenu.Item className={styles.item} onSelect={signOut}>
            <Icon name="signOut" />
            {t('shell.user.signOut')}
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
