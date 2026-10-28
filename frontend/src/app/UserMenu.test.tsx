import { cleanup, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ar from '../locales/ar.json';
import en from '../locales/en.json';
import { LANGUAGE_STORAGE_KEY } from './i18n';
import { GUEST, renderApp, testUser } from './test-utils';

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

describe('user menu', () => {
  it.each([
    ['ar', ar],
    ['en', en],
  ] as const)('calls the guest by its role in the UI language (%s)', async (lang, messages) => {
    // The guest's language comes from this browser (?lang=, then localStorage).
    localStorage.setItem(LANGUAGE_STORAGE_KEY, lang);
    const actor = userEvent.setup();
    await renderApp({ path: '/ask', user: GUEST });

    const trigger = await screen.findByRole('button', { name: messages.roles.guest });
    expect(trigger.textContent).toBe(messages.roles.guest);
    expect(screen.queryByText(GUEST.name)).toBeNull();

    await actor.click(trigger);
    const menu = within(await screen.findByRole('menu'));
    // Once, as the name: no account name, no email, and no role line repeating it.
    expect(menu.getAllByText(messages.roles.guest)).toHaveLength(1);
    expect(menu.queryByText(GUEST.name)).toBeNull();
    expect(menu.getByRole('menuitem', { name: messages.shell.user.signOut })).toBeDefined();
  });

  it("keeps a real user's own name, email and role", async () => {
    const user = testUser('editor', { name: 'ليلى تجريبية', preferred_language: 'en' });
    const actor = userEvent.setup();
    await renderApp({ path: '/ask', user });

    const trigger = await screen.findByRole('button', { name: user.name });
    expect(trigger.querySelector('[dir="rtl"]')?.textContent).toBe(user.name);
    expect(screen.queryByText(en.roles.guest)).toBeNull();

    await actor.click(trigger);
    const menu = within(await screen.findByRole('menu'));
    expect(menu.getByText(user.name)).toBeDefined();
    expect(menu.getByText(user.email)).toBeDefined();
    expect(menu.getByText(en.roles.editor)).toBeDefined();
  });
});
