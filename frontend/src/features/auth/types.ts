// Auth contract (SYSTEM_DESIGN §4, §7). B2 implements the endpoints; until its OpenAPI types
// are generated (make gen-api-types), these hand-written shapes are what the UI codes against.
import type { Language } from '../../app/i18n';

export type Role = 'viewer' | 'editor' | 'admin';

/** GET /api/me, and the body of POST /api/auth/login and /api/auth/guest. */
export interface Me {
  id: string;
  name: string;
  email: string;
  role: Role;
  preferred_language: Language;
  is_guest: boolean;
}

export interface Credentials {
  email: string;
  password: string;
}
