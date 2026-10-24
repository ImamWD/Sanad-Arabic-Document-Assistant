import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { useSession } from '../features/auth/session';
import { currentLanguage, hasExplicitLanguage, isLanguage } from './i18n';

/**
 * Applies the signed-in user's saved language (SYSTEM_DESIGN §8: URL, then the user's
 * preference, then localStorage, then English). Runs once per user, after a session restore
 * or a sign-in, and stands back if a language was chosen explicitly on this visit.
 */
export function ProfileLanguage() {
  const { i18n } = useTranslation();
  const { data: user } = useSession();
  const appliedFor = useRef<string | null>(null);

  useEffect(() => {
    if (!user) {
      appliedFor.current = null;
      return;
    }
    if (appliedFor.current === user.id) return;
    appliedFor.current = user.id;
    const preferred = user.preferred_language;
    if (!hasExplicitLanguage() && isLanguage(preferred) && preferred !== currentLanguage(i18n)) {
      void i18n.changeLanguage(preferred);
    }
  }, [user, i18n]);

  return null;
}
