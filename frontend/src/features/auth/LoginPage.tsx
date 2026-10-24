import { type SubmitEvent, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useLocation } from 'react-router';

import { Icon } from '../../lib/Icon';
import { useErrorMessage } from '../../lib/useErrorMessage';
import styles from './LoginPage.module.css';
import { useGuestLogin, useLogin, useSession } from './session';

const LANDING = '/ask';

/** Where to go after signing in: the page that sent us here, or Ask. */
function redirectTarget(state: unknown): string {
  if (typeof state !== 'object' || state === null || !('from' in state)) return LANDING;
  const from = state.from as Partial<Record<'pathname' | 'search' | 'hash', unknown>> | null;
  const { pathname, search, hash } = from ?? {};
  if (typeof pathname !== 'string' || !pathname.startsWith('/') || pathname === '/login') {
    return LANDING;
  }
  return (
    pathname + (typeof search === 'string' ? search : '') + (typeof hash === 'string' ? hash : '')
  );
}

export function LoginPage() {
  const { t } = useTranslation();
  const errorMessage = useErrorMessage();
  const location = useLocation();
  const session = useSession();
  const login = useLogin();
  const guest = useGuestLogin();
  const [missingFields, setMissingFields] = useState(false);
  const ids = { title: useId(), email: useId(), password: useId(), error: useId() };

  // Signed in, whether by this form, the guest button or an existing session: move on.
  if (session.data) return <Navigate to={redirectTarget(location.state)} replace />;

  const pending = login.isPending || guest.isPending;
  const error = login.error ?? guest.error;
  const message = missingFields ? t('auth.login.missingFields') : error ? errorMessage(error) : '';

  // A real <form> with a submit button, so Enter in either field signs in.
  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const field = (name: string) => {
      const value = data.get(name);
      return typeof value === 'string' ? value : '';
    };
    const email = field('email').trim();
    const password = field('password');
    guest.reset();
    setMissingFields(!email || !password);
    if (!email || !password) return;
    login.mutate({ email, password });
  };

  const continueAsGuest = () => {
    login.reset();
    setMissingFields(false);
    guest.mutate();
  };

  return (
    <section className={styles.card} aria-labelledby={ids.title}>
      <h1 id={ids.title} className={styles.title}>
        {t('app.title')}
      </h1>
      <p className={styles.intro}>{t('auth.login.intro')}</p>

      {/* noValidate: the browser's own validation bubbles speak the browser's language. */}
      <form className={styles.form} onSubmit={onSubmit} noValidate>
        <label className={styles.label} htmlFor={ids.email}>
          {t('auth.login.email')}
        </label>
        <input
          id={ids.email}
          className={styles.input}
          name="email"
          type="email"
          dir="auto"
          autoComplete="username"
          aria-describedby={message ? ids.error : undefined}
        />
        <label className={styles.label} htmlFor={ids.password}>
          {t('auth.login.password')}
        </label>
        <input
          id={ids.password}
          className={styles.input}
          name="password"
          type="password"
          autoComplete="current-password"
          aria-describedby={message ? ids.error : undefined}
        />
        {message && (
          <p id={ids.error} className={styles.error} role="alert">
            {message}
          </p>
        )}
        <button className={styles.primary} type="submit" disabled={pending}>
          {login.isPending ? t('auth.login.submitting') : t('auth.login.submit')}
        </button>
      </form>

      <div className={styles.divider}>
        <span>{t('auth.login.or')}</span>
      </div>
      <button
        className={styles.secondary}
        type="button"
        onClick={continueAsGuest}
        disabled={pending}
      >
        {t('auth.login.guest')}
        <Icon name="forward" />
      </button>
      <p className={styles.hint}>{t('auth.login.guestHint')}</p>
    </section>
  );
}
