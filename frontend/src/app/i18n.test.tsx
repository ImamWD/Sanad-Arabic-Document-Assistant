import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ar from '../locales/ar.json';
import en from '../locales/en.json';
import { initI18n, LANGUAGE_STORAGE_KEY } from './i18n';
import { LanguageSwitch } from './LanguageSwitch';

function visit(search: string) {
  window.history.replaceState({}, '', `/${search}`);
}

function htmlLangDir() {
  const root = document.documentElement;
  return { lang: root.lang, dir: root.dir };
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.lang = '';
  document.documentElement.dir = '';
  visit('');
});

afterEach(cleanup);

describe('locale entry points', () => {
  it('defaults to Arabic, right-to-left', async () => {
    await initI18n();
    expect(htmlLangDir()).toEqual({ lang: 'ar', dir: 'rtl' });
    expect(document.title).toBe(ar.app.title);
  });

  it('?lang=en selects English, left-to-right', async () => {
    visit('?lang=en');
    await initI18n();
    expect(htmlLangDir()).toEqual({ lang: 'en', dir: 'ltr' });
    expect(document.title).toBe(en.app.title);
  });

  it('?lang=ar wins over a stored English choice', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'en');
    visit('?lang=ar');
    await initI18n();
    expect(htmlLangDir()).toEqual({ lang: 'ar', dir: 'rtl' });
  });

  it('remembers the last choice when the URL has no ?lang=', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'en');
    await initI18n();
    expect(htmlLangDir()).toEqual({ lang: 'en', dir: 'ltr' });
  });

  it('maps a regional tag to its base language', async () => {
    visit('?lang=en-GB');
    await initI18n();
    expect(htmlLangDir()).toEqual({ lang: 'en', dir: 'ltr' });
  });

  it('falls back to Arabic for an unsupported ?lang=', async () => {
    visit('?lang=fr');
    await initI18n();
    expect(htmlLangDir()).toEqual({ lang: 'ar', dir: 'rtl' });
  });
});

describe('language switch', () => {
  it('flips lang, dir and title without any network request', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const i18n = await initI18n();
    render(
      <I18nextProvider i18n={i18n}>
        <LanguageSwitch />
      </I18nextProvider>,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: ar.language.switch }));
      await Promise.resolve();
    });

    expect(htmlLangDir()).toEqual({ lang: 'en', dir: 'ltr' });
    expect(document.title).toBe(en.app.title);
    expect(screen.getByRole('button', { name: en.language.switch }).lang).toBe('ar');
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en');
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
