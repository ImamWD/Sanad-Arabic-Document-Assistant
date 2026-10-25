import { act, cleanup, render, screen } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { initI18n } from '../../app/i18n';
import { AR_NUMBERING } from '../../lib/config';
import { createFormat } from '../../lib/format';
import ar from '../../locales/ar.json';
import en from '../../locales/en.json';
import type { Eta } from './askState';
import { WaitStatus } from './WaitStatus';

const NOW = Date.parse('2026-10-25T12:00:00Z');

beforeEach(() => {
  vi.useFakeTimers({ now: NOW });
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  window.history.replaceState({}, '', '/');
});

/** "{{name}}" placeholders filled in, to compare with what the screen shows. */
function fill(template: string, values: Record<string, string>): string {
  return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) => values[name] ?? '');
}

async function show(lang: 'ar' | 'en', eta: Eta) {
  window.history.replaceState({}, '', `/?lang=${lang}`);
  const i18n = await initI18n();
  render(
    <I18nextProvider i18n={i18n}>
      <WaitStatus stage="reading" position={null} sources={null} eta={eta} />
    </I18nextProvider>,
  );
  // useElapsedSeconds reads the clock on its first tick.
  await act(() => vi.advanceTimersByTimeAsync(1));
}

const eta = (expectedSeconds: number, capped = false, elapsedSeconds = 0): Eta => ({
  expectedSeconds,
  capped,
  since: NOW - elapsedSeconds * 1000,
});

const progress = () => screen.getByRole('progressbar');
const formatFor = (lang: 'ar' | 'en') => createFormat(lang, AR_NUMBERING);

describe('wait notice', () => {
  it.each([
    ['en', 45, en, '45 seconds'],
    ['en', 95, en, '2 minutes'],
    ['en', 300, en, '5 minutes'],
    ['ar', 45, ar, formatFor('ar').duration(45)],
    ['ar', 95, ar, 'دقيقتان'],
    ['ar', 300, ar, formatFor('ar').duration(300)],
  ] as const)('%s, %d s: "%s"', async (lang, seconds, messages, duration) => {
    await show(lang, eta(seconds));
    expect(screen.getByText(fill(messages.ask.wait.notice, { duration }))).toBeDefined();
    const elapsed = formatFor(lang).duration(0);
    expect(
      screen.getByText(fill(messages.ask.wait.elapsed, { elapsed, expected: duration })),
    ).toBeDefined();
    // A known estimate gets a bar that fills towards it.
    expect(progress().getAttribute('max')).toBe(String(seconds));
  });

  it('never shows a number above 90 seconds, however large the estimate', async () => {
    await show('en', eta(1474 / 3, false, 125));
    expect(screen.getByText(fill(en.ask.wait.notice, { duration: '8 minutes' }))).toBeDefined();
    expect(
      screen.getByText(fill(en.ask.wait.elapsed, { elapsed: '2 minutes', expected: '8 minutes' })),
    ).toBeDefined();
  });

  it.each([
    ['en', en],
    ['ar', ar],
  ] as const)(
    'a capped estimate says the server is busy, with no number (%s)',
    async (lang, messages) => {
      await show(lang, eta(600, true, 18));
      const status = screen.getByRole('status');
      expect(status.textContent).toContain(messages.ask.wait.busy);
      expect(status.textContent).not.toMatch(/\d/);
      expect(
        screen.getByText(
          fill(messages.ask.wait.elapsedOnly, {
            elapsed: formatFor(lang).duration(18),
          }),
        ),
      ).toBeDefined();
      // An indeterminate bar: no max, no value, so no claim of an end.
      expect(progress().hasAttribute('max')).toBe(false);
      expect(progress().hasAttribute('value')).toBe(false);
    },
  );

  it('treats an estimate of 600 seconds or more as busy, even when not marked capped', async () => {
    await show('en', eta(1474));
    expect(screen.getByRole('status').textContent).toContain(en.ask.wait.busy);
    expect(screen.queryByText(/1,474/)).toBeNull();
    expect(progress().hasAttribute('max')).toBe(false);
  });

  it('keeps the threshold: no notice at 20 seconds or less', async () => {
    await show('en', eta(20));
    expect(screen.getByRole('status').textContent).not.toContain('This answer may take');
    expect(
      screen.getByText(fill(en.ask.wait.elapsed, { elapsed: '0 seconds', expected: '20 seconds' })),
    ).toBeDefined();
  });

  it('keeps the overrun message past 1.25 times the estimate, in minutes', async () => {
    await show('en', eta(120, false, 151));
    expect(screen.getByText(fill(en.ask.wait.overrun, { elapsed: '3 minutes' }))).toBeDefined();
    expect(progress().hasAttribute('max')).toBe(false);
  });
});
