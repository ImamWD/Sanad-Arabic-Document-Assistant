import { cleanup, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LANGUAGE_STORAGE_KEY } from '../../app/i18n';
import { apiError, GUEST, json, renderApp, testUser } from '../../app/test-utils';
import ar from '../../locales/ar.json';
import { makeDocument } from '../library/test-fixtures';
import en from '../../locales/en.json';

beforeEach(() => {
  localStorage.clear();
  // Start in Arabic through a stored choice: not explicit, so the profile language still applies.
  localStorage.setItem(LANGUAGE_STORAGE_KEY, 'ar');
  window.history.replaceState({}, '', '/');
});

afterEach(cleanup);

const VIEWER = testUser('viewer');

async function fillIn(actor: ReturnType<typeof userEvent.setup>, password = 'not-a-real-password') {
  await actor.type(await screen.findByLabelText(ar.auth.login.email), VIEWER.email);
  await actor.type(screen.getByLabelText(ar.auth.login.password), password);
}

describe('login page', () => {
  it('pressing Enter in the password field signs in and lands on Ask', async () => {
    const actor = userEvent.setup();
    const { calls, router } = await renderApp({
      path: '/login',
      handlers: { 'POST /api/auth/login': () => json(200, VIEWER) },
    });

    await fillIn(actor);
    await actor.keyboard('{Enter}');

    expect(await screen.findByRole('heading', { name: ar.pages.ask.title })).toBeDefined();
    expect(router.state.location.pathname).toBe('/ask');
    const posts = calls.filter((c) => c.method === 'POST');
    expect(posts).toEqual([
      {
        method: 'POST',
        path: '/api/auth/login',
        body: { email: VIEWER.email, password: 'not-a-real-password' },
      },
    ]);
  });

  it('"Continue as guest" signs in as the guest and lands on Ask', async () => {
    const actor = userEvent.setup();
    const { calls, router } = await renderApp({
      path: '/login',
      handlers: { 'POST /api/auth/guest': () => json(200, GUEST) },
    });

    await actor.click(await screen.findByRole('button', { name: ar.auth.login.guest }));

    expect(await screen.findByRole('heading', { name: ar.pages.ask.title })).toBeDefined();
    expect(router.state.location.pathname).toBe('/ask');
    expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual([
      '/api/auth/guest',
    ]);
  });

  it('translates the server error code', async () => {
    const actor = userEvent.setup();
    const { router } = await renderApp({
      path: '/login',
      handlers: { 'POST /api/auth/login': () => apiError(401, 'INVALID_CREDENTIALS') },
    });

    await fillIn(actor, 'wrong-password');
    await actor.click(screen.getByRole('button', { name: ar.auth.login.submit }));

    expect((await screen.findByRole('alert')).textContent).toBe(ar.errors.INVALID_CREDENTIALS);
    expect(router.state.location.pathname).toBe('/login');
  });

  it('the message follows a language switch', async () => {
    const actor = userEvent.setup();
    await renderApp({
      path: '/login',
      handlers: { 'POST /api/auth/guest': () => apiError(403, 'GUEST_DISABLED') },
    });

    await actor.click(await screen.findByRole('button', { name: ar.auth.login.guest }));
    expect((await screen.findByRole('alert')).textContent).toBe(ar.errors.GUEST_DISABLED);

    await actor.click(screen.getByRole('button', { name: ar.language.switch }));
    expect(screen.getByRole('alert').textContent).toBe(en.errors.GUEST_DISABLED);
  });

  it('never shows server prose, even when the server sends some', async () => {
    const actor = userEvent.setup();
    await renderApp({
      path: '/login',
      handlers: {
        'POST /api/auth/login': () => json(500, { detail: 'psycopg.OperationalError at line 42' }),
      },
    });

    await fillIn(actor);
    await actor.keyboard('{Enter}');

    expect((await screen.findByRole('alert')).textContent).toBe(ar.errors.UNKNOWN_ERROR);
    expect(screen.queryByText(/psycopg/)).toBeNull();
  });

  it('asks for both fields instead of sending an empty form', async () => {
    const actor = userEvent.setup();
    const { calls } = await renderApp({ path: '/login' });

    await actor.type(await screen.findByLabelText(ar.auth.login.email), '{Enter}');

    expect((await screen.findByRole('alert')).textContent).toBe(ar.auth.login.missingFields);
    expect(calls.filter((c) => c.method === 'POST')).toEqual([]);
  });

  it('returns to the page that required sign-in', async () => {
    const actor = userEvent.setup();
    const doc = makeDocument({ id: 'doc-7', status: 'queued', page_count: null });
    const { router } = await renderApp({
      path: '/documents/doc-7?page=3',
      handlers: {
        'POST /api/auth/login': () => json(200, VIEWER),
        'GET /api/documents/doc-7': () => json(200, doc),
      },
    });

    await fillIn(actor);
    await actor.keyboard('{Enter}');

    expect(await screen.findByRole('heading', { level: 1, name: doc.title })).toBeDefined();
    expect(router.state.location.pathname + router.state.location.search).toBe(
      '/documents/doc-7?page=3',
    );
  });

  it('sends a signed-in user straight on to Ask', async () => {
    const { router } = await renderApp({ path: '/login', user: VIEWER });
    expect(await screen.findByRole('heading', { name: ar.pages.ask.title })).toBeDefined();
    expect(router.state.location.pathname).toBe('/ask');
  });

  it('keeps what was typed when the language switches', async () => {
    const actor = userEvent.setup();
    await renderApp({ path: '/login' });
    await actor.type(await screen.findByLabelText(ar.auth.login.email), VIEWER.email);

    await actor.click(screen.getByRole('button', { name: ar.language.switch }));

    expect(document.documentElement.dir).toBe('ltr');
    expect(screen.getByLabelText<HTMLInputElement>(en.auth.login.email).value).toBe(VIEWER.email);
  });

  it('offers the language switch before sign-in, and switching makes no request', async () => {
    const actor = userEvent.setup();
    const { calls } = await renderApp({ path: '/login' });
    await screen.findByLabelText(ar.auth.login.email);
    const before = calls.length;

    await actor.click(screen.getByRole('button', { name: ar.language.switch }));

    expect(document.documentElement).toMatchObject({ lang: 'en', dir: 'ltr' });
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(en.app.title);
    expect(screen.getByLabelText(en.auth.login.email)).toBeDefined();
    expect(calls.length).toBe(before);
  });
});
