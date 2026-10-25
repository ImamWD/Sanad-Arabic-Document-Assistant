import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { useTranslation } from 'react-i18next';

import { Icon } from '../../lib/Icon';
import type { LifecycleAction } from './api';
import styles from './RowActions.module.css';
import type { DocumentItem } from './types';

export type RowAction = LifecycleAction | 'restrict' | 'unrestrict' | 'edit';

interface RowActionsProps {
  document: DocumentItem;
  busy: boolean;
  onAction: (action: RowAction) => void;
}

/** An editor's actions on one Library row. */
export function RowActions({ document, busy, onAction }: RowActionsProps) {
  const { t } = useTranslation();
  const item = (action: RowAction, label: string) => (
    <DropdownMenu.Item
      className={styles.item}
      onSelect={() => {
        onAction(action);
      }}
    >
      {label}
    </DropdownMenu.Item>
  );

  return (
    // modal={false}: the modal variant injects a <style> element, which the CSP blocks.
    <DropdownMenu.Root modal={false}>
      <DropdownMenu.Trigger
        className={styles.trigger}
        disabled={busy}
        aria-label={t('library.actions.menu', { title: document.title })}
      >
        <Icon name="chevronDown" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className={styles.content} align="end" sideOffset={4}>
          {item('edit', t('library.actions.edit'))}
          {document.restricted
            ? item('unrestrict', t('library.actions.unrestrict'))
            : item('restrict', t('library.actions.restrict'))}
          {document.status === 'failed' && item('retry', t('library.actions.retry'))}
          <DropdownMenu.Separator className={styles.separator} />
          {document.is_archived
            ? item('unarchive', t('library.actions.unarchive'))
            : item('archive', t('library.actions.archive'))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
