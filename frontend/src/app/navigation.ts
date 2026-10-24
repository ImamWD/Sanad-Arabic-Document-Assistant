import { hasRole } from '../features/auth/roles';
import type { Me, Role } from '../features/auth/types';
import type { IconName } from '../lib/Icon';

export interface NavItem {
  /** Also the label key: shell.nav.<id>. */
  id: 'ask' | 'library' | 'upload' | 'admin';
  path: string;
  icon: IconName;
  minRole: Role;
}

// Navigation by role (brief §5): viewers ask and browse, editors also upload, admins also
// manage users. The server enforces the same rules; this only hides what a role can't use.
export const NAV_ITEMS: readonly NavItem[] = [
  { id: 'ask', path: '/ask', icon: 'ask', minRole: 'viewer' },
  { id: 'library', path: '/library', icon: 'library', minRole: 'viewer' },
  { id: 'upload', path: '/upload', icon: 'upload', minRole: 'editor' },
  { id: 'admin', path: '/admin', icon: 'admin', minRole: 'admin' },
];

export function navItemsFor(user: Pick<Me, 'role'>): NavItem[] {
  return NAV_ITEMS.filter((item) => hasRole(user, item.minRole));
}
