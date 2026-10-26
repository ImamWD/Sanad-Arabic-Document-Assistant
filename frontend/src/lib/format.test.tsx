import { act, cleanup, render, screen } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import { afterEach, describe, expect, it } from 'vitest';

import { initI18n } from '../app/i18n';
import { createFormat, localeTag, parseArabicNumbering } from './format';
import { useFormat } from './useFormat';

afterEach(cleanup);

// ICU puts invisible direction marks around some Arabic symbols (٪, minus). Compare without them.
const plain = (text: string) => text.replace(/[؜‎‏]/gu, '');

const MARCH_15 = '2021-03-15T12:00:00Z';
const LONG_UTC: Intl.DateTimeFormatOptions = {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
};

describe('locale tag', () => {
  it('always names the Arabic numbering system explicitly', () => {
    expect(localeTag('ar', 'arab')).toBe('ar-u-nu-arab');
    expect(localeTag('ar', 'latn')).toBe('ar-u-nu-latn');
    expect(localeTag('en', 'arab')).toBe('en');
  });

  it('reads VITE_AR_NUMBERING, defaulting to Latin digits (Q6)', () => {
    expect(parseArabicNumbering('latn')).toBe('latn');
    expect(parseArabicNumbering('arab')).toBe('arab');
    expect(parseArabicNumbering(undefined)).toBe('latn');
    expect(parseArabicNumbering('roman')).toBe('latn');
  });
});

describe.each([
  {
    name: 'Arabic, Arabic-Indic digits (VITE_AR_NUMBERING=arab)',
    format: createFormat('ar', 'arab'),
    number: '١٬٢٣٤٫٥',
    date: '١٥ مارس ٢٠٢١',
    percent: '٢٥٪',
    yesterday: 'أمس',
    inThreeDays: 'خلال ٣ أيام',
    fiveMinutesAgo: 'قبل ٥ دقائق',
    durations: ['٤٥ ثانية', 'دقيقتان', '٥ دقائق', '١١ دقيقة'],
  },
  {
    name: 'Arabic, Latin digits (the default)',
    format: createFormat('ar', 'latn'),
    number: '1,234.5',
    date: '15 مارس 2021',
    percent: '25%',
    yesterday: 'أمس',
    inThreeDays: 'خلال 3 أيام',
    fiveMinutesAgo: 'قبل 5 دقائق',
    durations: ['45 ثانية', 'دقيقتان', '5 دقائق', '11 دقيقة'],
  },
  {
    name: 'English',
    format: createFormat('en', 'arab'),
    number: '1,234.5',
    date: 'March 15, 2021',
    percent: '25%',
    yesterday: 'yesterday',
    inThreeDays: 'in 3 days',
    fiveMinutesAgo: '5 minutes ago',
    durations: ['45 seconds', '2 minutes', '5 minutes', '11 minutes'],
  },
])('$name', ({ format, ...want }) => {
  it('formats numbers', () => {
    expect(plain(format.number(1234.5))).toBe(want.number);
  });

  it('formats dates', () => {
    expect(plain(format.date(MARCH_15, LONG_UTC))).toBe(want.date);
    expect(plain(format.date(new Date(MARCH_15), LONG_UTC))).toBe(want.date);
  });

  it('formats percentages from ratios', () => {
    expect(plain(format.percent(0.25))).toBe(want.percent);
  });

  it('formats relative times', () => {
    expect(format.relative(-1, 'day')).toBe(want.yesterday);
    expect(plain(format.relative(3, 'day'))).toBe(want.inThreeDays);
    const now = Date.parse(MARCH_15);
    expect(plain(format.since(now - 5 * 60_000, now))).toBe(want.fiveMinutesAgo);
  });

  it('says durations in seconds below 90 and in minutes from there, with the right plural', () => {
    expect([45, 95, 300, 660].map((seconds) => plain(format.duration(seconds)))).toEqual(
      want.durations,
    );
  });
});

describe('duration()', () => {
  const format = createFormat('en', 'latn');

  it('never says more than 89 seconds', () => {
    expect(format.duration(89)).toBe('89 seconds');
    expect(format.duration(89.6)).toBe('2 minutes');
    expect(format.duration(90)).toBe('2 minutes');
    expect(format.duration(1474)).toBe('25 minutes');
  });

  it('rounds, and never goes below zero', () => {
    expect(format.duration(44.4)).toBe('44 seconds');
    expect(format.duration(-3)).toBe('0 seconds');
  });
});

describe('since() picks the largest unit that fits', () => {
  const format = createFormat('en', 'latn');
  const now = Date.parse(MARCH_15);

  it.each([
    [0, 'now'],
    [-30_000, '30 seconds ago'],
    [-3 * 3600_000, '3 hours ago'],
    [2 * 24 * 3600_000, 'in 2 days'],
    [-400 * 24 * 3600_000, 'last year'],
  ])('%i ms → %s', (offset, text) => {
    expect(format.since(now + offset, now)).toBe(text);
  });
});

function Probe() {
  const format = useFormat();
  return <output>{format.date(MARCH_15, LONG_UTC)}</output>;
}

describe('useFormat()', () => {
  it('follows the active language, with Latin digits by default', async () => {
    window.history.replaceState({}, '', '/?lang=ar');
    const i18n = await initI18n();
    render(
      <I18nextProvider i18n={i18n}>
        <Probe />
      </I18nextProvider>,
    );
    expect(plain(screen.getByRole('status').textContent)).toBe('15 مارس 2021');

    await act(() => i18n.changeLanguage('en'));
    expect(screen.getByRole('status').textContent).toBe('March 15, 2021');
  });
});
