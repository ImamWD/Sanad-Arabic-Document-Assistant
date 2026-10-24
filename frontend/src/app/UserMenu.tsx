import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { useCurrentUser, useLogout } from '../features/auth/session';
import { Bidi } from '../lib/BidiText';
import { Icon } from '../lib/Icon';
import styles from './UserMenu.module.css';

export function UserMenu() {
  const { t } = useTranslation();
  const user = useCurrentUser();
  const logout = useLogout();
  const navigate = useNavigate();
  const role = user.is_guest ? t('roles.guest') : t(`roles.${user.role}`);

  const signOut = () => {
    logout.mutate(undefined, { onSettled: () => void navigate('/login', { replace: true }) });
  };

  return (
    // modal={false}: the modal variant locks scrolling by injecting a <style> element, which
    // the Content-Security-Policy (style-src 'self') blocks.
    <DropdownMenu.Root modal={false}>
      <DropdownMenu.Trigger className={styles.trigger}>
        <Icon name="user" />
        <Bidi className={styles.name} text={user.name} />
        <Icon name="chevronDown" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className={styles.content} align="end" sideOffset={6}>
          <DropdownMenu.Label className={styles.label}>
            <Bidi as="div" className={styles.labelName} text={user.name} />
            {!user.is_guest && <Bidi as="div" className={styles.labelMeta} text={user.email} />}
            <div className={styles.labelMeta}>{role}</div>
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
