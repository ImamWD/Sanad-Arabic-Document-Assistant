import type { Me, Role } from './types';

const RANK: Record<Role, number> = { viewer: 0, editor: 1, admin: 2 };

/** Roles are cumulative: an editor can do everything a viewer can, an admin everything. */
export function hasRole(user: Pick<Me, 'role'>, minimum: Role): boolean {
  return RANK[user.role] >= RANK[minimum];
}
