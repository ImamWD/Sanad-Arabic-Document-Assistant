import { describe, expect, it } from 'vitest';

import ar from './ar.json';
import en from './en.json';

interface Messages {
  [key: string]: string | Messages;
}

function flatten(messages: Messages, prefix = ''): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, value] of Object.entries(messages)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === 'string') out.set(path, value);
    else for (const [k, v] of flatten(value, path)) out.set(k, v);
  }
  return out;
}

const locales = { ar: flatten(ar), en: flatten(en) };

describe('locale files', () => {
  it('ar.json and en.json have identical key sets', () => {
    const arKeys = [...locales.ar.keys()].sort();
    const enKeys = [...locales.en.keys()].sort();
    expect(arKeys.filter((k) => !locales.en.has(k))).toEqual([]);
    expect(enKeys.filter((k) => !locales.ar.has(k))).toEqual([]);
    expect(arKeys).toEqual(enKeys);
  });

  it.each(Object.entries(locales))('%s.json has no empty strings', (_name, messages) => {
    const empty = [...messages].filter(([, v]) => v.trim() === '').map(([k]) => k);
    expect(empty).toEqual([]);
  });

  it('Arabic strings are actually Arabic', () => {
    const arabic = /[؀-ۿ]/;
    // language.switch names the *other* language, so it is English by design.
    const notArabic = [...locales.ar]
      .filter(([k, v]) => k !== 'language.switch' && !arabic.test(v))
      .map(([k]) => k);
    expect(notArabic).toEqual([]);
  });
});
