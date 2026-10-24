import { act, cleanup, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { apiFetch } from '../lib/api';
import iconStyles from '../lib/Icon.module.css';
import ar from '../locales/ar.json';
import en from '../locales/en.json';
import { apiError, GUEST, json, renderApp, testUser } from './test-utils';

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, '', '/');
  // Radix measures its popper with ResizeObserver, which jsdom lacks.
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();
    },
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const navLabels = (messages: typeof ar | typeof en = ar) =>
  within(screen.getByRole('navigation', { name: messages.shell.nav.label }))
    .getAllByRole('link')
    .map((link) => link.textContent);

describe('routing', () => {
  it('sends a visitor without a session to the login page', async () => {
    const { router } = await renderApp({ path: '/library' });
    expect(await screen.findByRole('heading', { level: 1, name: ar.app.title })).toBeDefined();
    expect(router.state.location.pathname).toBe('/login');
    expect(screen.getByRole('button', { name: ar.language.switch })).toBeDefined();
  });

  it('opens Ask at / for a signed-in user', async () => {
    const { router } = await renderApp({ path: '/', user: testUser('viewer') });
    expect(await screen.findByRole('heading', { name: ar.pages.ask.title })).toBeDefined();
    expect(router.state.location.pathname).toBe('/ask');
  });

  it('shows a not-found page for unknown routes', async () => {
    await renderApp({ path: '/nowhere', user: testUser('viewer') });
    expect(await screen.findByRole('heading', { name: ar.pages.notFound.title })).toBeDefined();
  });

  it('opens a document at the requested page, with localised digits', async () => {
    await renderApp({ path: '/documents/doc-7?page=12', user: testUser('viewer') });
    expect(await screen.findByText('الصفحة ١٢')).toBeDefined();
    expect(screen.getByText('doc-7').getAttribute('dir')).toBe('auto');
  });

  it('a 401 from any request ends the session and returns to login', async () => {
    const { queryClient, router } = await renderApp({
      path: '/library',
      user: testUser('viewer'),
      handlers: { 'GET /api/documents': () => apiError(401, 'UNAUTHENTICATED') },
    });
    await screen.findByRole('heading', { name: ar.pages.library.title });
    await act(() =>
      queryClient
        .query({ queryKey: ['documents'], queryFn: () => apiFetch('/documents') })
        .catch(() => undefined),
    );
    expect(await screen.findByRole('button', { name: ar.auth.login.submit })).toBeDefined();
    expect(router.state.location.pathname).toBe('/login');
  });
});

describe('navigation by role', () => {
  it.each([
    ['viewer', [ar.shell.nav.ask, ar.shell.nav.library]],
    ['editor', [ar.shell.nav.ask, ar.shell.nav.library, ar.shell.nav.upload]],
    ['admin', [ar.shell.nav.ask, ar.shell.nav.library, ar.shell.nav.upload, ar.shell.nav.admin]],
  ] as const)('%s sees %j', async (role, labels) => {
    await renderApp({ path: '/ask', user: testUser(role) });
    await screen.findByRole('heading', { name: ar.pages.ask.title });
    expect(navLabels()).toEqual(labels);
  });

  it('a guest navigates like a viewer', async () => {
    await renderApp({ path: '/ask', user: GUEST });
    await screen.findByRole('heading', { name: ar.pages.ask.title });
    expect(navLabels()).toEqual([ar.shell.nav.ask, ar.shell.nav.library]);
  });

  it('marks the current page in the navigation', async () => {
    await renderApp({ path: '/library', user: testUser('viewer') });
    const link = await screen.findByRole('link', { name: ar.shell.nav.library });
    expect(link.getAttribute('aria-current')).toBe('page');
  });

  it.each([
    ['viewer', '/upload', ar.pages.forbidden.title],
    ['viewer', '/admin', ar.pages.forbidden.title],
    ['editor', '/upload', ar.pages.upload.title],
    ['editor', '/admin', ar.pages.forbidden.title],
    ['admin', '/admin', ar.pages.admin.title],
  ] as const)('%s at %s sees "%s"', async (role, path, heading) => {
    await renderApp({ path, user: testUser(role) });
    expect(await screen.findByRole('heading', { name: heading })).toBeDefined();
  });
});

describe('header', () => {
  it('shows the app name, the language switch and the user menu', async () => {
    const user = testUser('editor');
    await renderApp({ path: '/ask', user });
    expect(await screen.findByRole('link', { name: ar.app.name })).toBeDefined();
    expect(screen.getByRole('button', { name: ar.language.switch })).toBeDefined();
    expect(screen.getByRole('button', { name: user.name })).toBeDefined();
  });

  it('switching language mirrors the shell without any request', async () => {
    const actor = userEvent.setup();
    const { calls } = await renderApp({ path: '/ask', user: testUser('admin') });
    await screen.findByRole('heading', { name: ar.pages.ask.title });
    const before = calls.length;

    await actor.click(screen.getByRole('button', { name: ar.language.switch }));

    expect(document.documentElement.dir).toBe('ltr');
    expect(screen.getByRole('heading', { name: en.pages.ask.title })).toBeDefined();
    expect(navLabels(en)).toEqual([
      en.shell.nav.ask,
      en.shell.nav.library,
      en.shell.nav.upload,
      en.shell.nav.admin,
    ]);
    expect(calls.length).toBe(before);
  });

  it('feeds Radix the active direction, and follows a switch', async () => {
    const actor = userEvent.setup();
    const user = testUser('viewer');
    await renderApp({ path: '/ask', user });

    await actor.click(await screen.findByRole('button', { name: user.name }));
    expect((await screen.findByRole('menu')).getAttribute('dir')).toBe('rtl');
    await actor.keyboard('{Escape}');

    await actor.click(screen.getByRole('button', { name: ar.language.switch }));
    await actor.click(screen.getByRole('button', { name: user.name }));
    expect((await screen.findByRole('menu')).getAttribute('dir')).toBe('ltr');
  });

  it('signs out from the user menu and returns to login', async () => {
    const actor = userEvent.setup();
    const user = testUser('viewer');
    const { calls, router } = await renderApp({
      path: '/ask',
      user,
      handlers: { 'POST /api/auth/logout': () => new Response(null, { status: 204 }) },
    });

    await actor.click(await screen.findByRole('button', { name: user.name }));
    const menu = await screen.findByRole('menu');
    expect(within(menu).getByText(ar.roles.viewer)).toBeDefined();
    await actor.click(within(menu).getByRole('menuitem', { name: ar.shell.user.signOut }));

    expect(await screen.findByRole('button', { name: ar.auth.login.submit })).toBeDefined();
    expect(router.state.location.pathname).toBe('/login');
    expect(calls.some((c) => c.method === 'POST' && c.path === '/api/auth/logout')).toBe(true);
  });

  it('after signing out, the next sign-in lands on Ask, not the previous page', async () => {
    const actor = userEvent.setup();
    const user = testUser('admin');
    const { router } = await renderApp({
      path: '/library',
      user,
      handlers: {
        'POST /api/auth/logout': () => new Response(null, { status: 204 }),
        'POST /api/auth/guest': () => json(200, GUEST),
      },
    });

    await actor.click(await screen.findByRole('button', { name: user.name }));
    await actor.click(await screen.findByRole('menuitem', { name: ar.shell.user.signOut }));
    await actor.click(await screen.findByRole('button', { name: ar.auth.login.guest }));

    expect(await screen.findByRole('heading', { name: ar.pages.ask.title })).toBeDefined();
    expect(router.state.location.pathname).toBe('/ask');
  });

  it('labels a guest as a guest', async () => {
    const actor = userEvent.setup();
    await renderApp({ path: '/ask', user: GUEST });
    await actor.click(await screen.findByRole('button', { name: GUEST.name }));
    expect(within(await screen.findByRole('menu')).getByText(ar.roles.guest)).toBeDefined();
  });
});

describe('directional icons', () => {
  it('only arrow-like icons are marked to mirror', async () => {
    const actor = userEvent.setup();
    const user = testUser('admin');
    await renderApp({ path: '/ask', user });
    await actor.click(await screen.findByRole('button', { name: user.name }));
    const icons = [...document.querySelectorAll<SVGElement>('svg[data-icon]')];
    const mirrored = icons
      .filter((icon) => icon.classList.contains(String(iconStyles.mirror)))
      .map((icon) => icon.dataset.icon);
    expect(mirrored).toEqual(['signOut']);
    expect(icons.map((icon) => icon.dataset.icon)).toContain('ask');
  });
});
