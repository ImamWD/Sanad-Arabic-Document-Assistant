// Language precedence (SYSTEM_DESIGN §8, manager ruling of 24 Oct):
//   session restore: ?lang= → the user's preferred_language → localStorage → en
//   right after sign-in: a language chosen on this visit (?lang= or the switch) is kept and
//   saved with PATCH /api/me; otherwise the profile's language applies.
// The guest never PATCHes (a shared account). A language switch never GETs.
import { cleanup, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import ar from '../locales/ar.json';
import en from '../locales/en.json';
import { LANGUAGE_STORAGE_KEY } from './i18n';
import { type ApiCall, GUEST, json, renderApp, testUser } from './test-utils';

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, '', '/');
});

afterEach(cleanup);

const htmlLang = () => document.documentElement.lang;
const patches = (calls: ApiCall[]) => calls.filter((c) => c.method === 'PATCH');
const gets = (calls: ApiCall[]) => calls.filter((c) => c.method === 'GET');
const PATCH_OK = { 'PATCH /api/me': () => new Response(null, { status: 204 }) };

describe('session restore', () => {
  it("the user's saved language beats the last choice in localStorage", async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'ar');
    const user = testUser('viewer', { preferred_language: 'en' });
    const { calls } = await renderApp({ path: '/ask', user });

    expect(await screen.findByRole('heading', { name: en.pages.ask.title })).toBeDefined();
    expect(htmlLang()).toBe('en');
    expect(patches(calls)).toEqual([]);
  });

  it('?lang= in the URL beats the saved language, and is not saved', async () => {
    window.history.replaceState({}, '', '/ask?lang=ar');
    const user = testUser('viewer', { preferred_language: 'en' });
    const { calls } = await renderApp({ path: '/ask', user });

    expect(await screen.findByRole('heading', { name: ar.pages.ask.title })).toBeDefined();
    expect(htmlLang()).toBe('ar');
    expect(patches(calls)).toEqual([]);
  });

  it('with nothing stored, the saved language replaces the English default', async () => {
    const user = testUser('editor', { preferred_language: 'ar' });
    await renderApp({ path: '/ask', user });
    expect(await screen.findByRole('heading', { name: ar.pages.ask.title })).toBeDefined();
    expect(document.documentElement.dir).toBe('rtl');
  });
});

describe('right after sign-in', () => {
  async function signIn(actor: ReturnType<typeof userEvent.setup>, messages: typeof en) {
    await actor.type(await screen.findByLabelText(messages.auth.login.email), 'viewer@example.org');
    await actor.type(
      screen.getByLabelText(messages.auth.login.password),
      'not-a-real-password{Enter}',
    );
  }

  it('an untouched language gives way to the saved one, and nothing is saved', async () => {
    const actor = userEvent.setup();
    const user = testUser('viewer', { preferred_language: 'ar' });
    const { calls } = await renderApp({
      path: '/login',
      handlers: { 'POST /api/auth/login': () => json(200, user), ...PATCH_OK },
    });

    await signIn(actor, en);

    expect(await screen.findByRole('heading', { name: ar.pages.ask.title })).toBeDefined();
    expect(patches(calls)).toEqual([]);
  });

  it('a language picked with the switch is kept and saved to the profile', async () => {
    const actor = userEvent.setup();
    const user = testUser('viewer', { preferred_language: 'en' });
    const { calls } = await renderApp({
      path: '/login',
      handlers: { 'POST /api/auth/login': () => json(200, user), ...PATCH_OK },
    });

    await actor.click(await screen.findByRole('button', { name: en.language.switch }));
    expect(patches(calls)).toEqual([]); // nobody to save it for yet
    await signIn(actor, ar);

    expect(await screen.findByRole('heading', { name: ar.pages.ask.title })).toBeDefined();
    expect(patches(calls)).toEqual([
      { method: 'PATCH', path: '/api/me', body: { preferred_language: 'ar' } },
    ]);
  });

  it('a language from ?lang= is kept and saved to the profile', async () => {
    window.history.replaceState({}, '', '/login?lang=ar');
    const actor = userEvent.setup();
    const user = testUser('viewer', { preferred_language: 'en' });
    const { calls } = await renderApp({
      path: '/login',
      handlers: { 'POST /api/auth/login': () => json(200, user), ...PATCH_OK },
    });

    await signIn(actor, ar);

    expect(await screen.findByRole('heading', { name: ar.pages.ask.title })).toBeDefined();
    expect(patches(calls)).toEqual([
      { method: 'PATCH', path: '/api/me', body: { preferred_language: 'ar' } },
    ]);
  });

  it('nothing is saved when the choice already matches the profile', async () => {
    window.history.replaceState({}, '', '/login?lang=en');
    const actor = userEvent.setup();
    const user = testUser('viewer', { preferred_language: 'en' });
    const { calls } = await renderApp({
      path: '/login',
      handlers: { 'POST /api/auth/login': () => json(200, user), ...PATCH_OK },
    });

    await signIn(actor, en);

    expect(await screen.findByRole('heading', { name: en.pages.ask.title })).toBeDefined();
    expect(patches(calls)).toEqual([]);
  });

  it('the guest keeps a picked language but never saves it', async () => {
    const actor = userEvent.setup();
    const guest = { ...GUEST, preferred_language: 'en' as const };
    const { calls } = await renderApp({
      path: '/login',
      handlers: { 'POST /api/auth/guest': () => json(200, guest), ...PATCH_OK },
    });

    await actor.click(await screen.findByRole('button', { name: en.language.switch }));
    await actor.click(screen.getByRole('button', { name: ar.auth.login.guest }));

    expect(await screen.findByRole('heading', { name: ar.pages.ask.title })).toBeDefined();
    expect(patches(calls)).toEqual([]);
  });
});

describe('switching language while signed in', () => {
  it('saves a real user’s choice with PATCH /api/me and makes no GET', async () => {
    const actor = userEvent.setup();
    const user = testUser('editor', { preferred_language: 'en' });
    const { calls } = await renderApp({ path: '/library', user, handlers: PATCH_OK });
    await screen.findByRole('heading', { name: en.pages.library.title });
    const getsBefore = gets(calls).length;

    await actor.click(screen.getByRole('button', { name: en.language.switch }));
    await actor.click(screen.getByRole('button', { name: ar.language.switch }));

    expect(htmlLang()).toBe('en');
    expect(patches(calls).map((c) => c.body)).toEqual([
      { preferred_language: 'ar' },
      { preferred_language: 'en' },
    ]);
    expect(gets(calls).length).toBe(getsBefore);
  });

  it('ignores a failed save (404 until B2 lands): no message, the switch still happens', async () => {
    const actor = userEvent.setup();
    const user = testUser('viewer', { preferred_language: 'en' });
    const { calls } = await renderApp({ path: '/ask', user }); // PATCH falls through to 404
    await screen.findByRole('heading', { name: en.pages.ask.title });

    await actor.click(screen.getByRole('button', { name: en.language.switch }));

    expect(await screen.findByRole('heading', { name: ar.pages.ask.title })).toBeDefined();
    expect(patches(calls)).toHaveLength(1);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('never saves the shared guest account’s language', async () => {
    const actor = userEvent.setup();
    const { calls } = await renderApp({
      path: '/ask',
      user: { ...GUEST, preferred_language: 'en' },
      handlers: PATCH_OK,
    });
    await screen.findByRole('heading', { name: en.pages.ask.title });

    await actor.click(screen.getByRole('button', { name: en.language.switch }));

    expect(htmlLang()).toBe('ar');
    expect(patches(calls)).toEqual([]);
  });
});
