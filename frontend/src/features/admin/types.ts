// The admin users contract (SYSTEM_DESIGN §7), taken from the generated OpenAPI types (B2).
import type { components } from '../../api/schema';
import type { Language } from '../../app/i18n';
import type { Role } from '../auth/types';

/** One row of GET /api/admin/users, and the body POST and PATCH return. */
export type AdminUser = components['schemas']['AdminUser'];

/** POST /api/admin/users. The server rejects any other field. */
export type NewUser = components['schemas']['UserCreate'];

/** PATCH /api/admin/users/{id}. Only the fields present are changed. */
export type UserChanges = components['schemas']['UserUpdate'];

export const ROLES: readonly Role[] = ['viewer', 'editor', 'admin'];
export const LANGUAGES: readonly Language[] = ['ar', 'en'];
