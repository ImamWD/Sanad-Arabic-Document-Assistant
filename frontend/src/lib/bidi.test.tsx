import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { Bidi } from './BidiText';
import { splitBidi } from './bidi';
import styles from './BidiText.module.css';

afterEach(cleanup);

// The regression fixture from SYSTEM_DESIGN §8.
const FIXTURE = 'تم تمويل المشروع YEP-2021-03 عبر https://example.org/r في ٢٠٢١';

const isolated = (text: string) =>
  splitBidi(text)
    .filter((s) => s.isolate)
    .map((s) => s.text);

describe('splitBidi', () => {
  it('isolates the code and the URL of the fixture, and nothing else', () => {
    expect(splitBidi(FIXTURE)).toEqual([
      { text: 'تم تمويل المشروع ', isolate: false },
      { text: 'YEP-2021-03', isolate: true },
      { text: ' عبر ', isolate: false },
      { text: 'https://example.org/r', isolate: true },
      { text: ' في ٢٠٢١', isolate: false },
    ]);
  });

  it('never changes the text itself', () => {
    expect(
      splitBidi(FIXTURE)
        .map((s) => s.text)
        .join(''),
    ).toBe(FIXTURE);
  });

  it('keeps a multi-word English phrase in one run, so its words stay in order', () => {
    expect(isolated('قدّم برنامج Youth Employment Programme دعمًا للشباب')).toEqual([
      'Youth Employment Programme',
    ]);
  });

  it('leaves sentence punctuation after a URL or code outside the run', () => {
    expect(isolated('راجع https://example.org/r.')).toEqual(['https://example.org/r']);
    expect(isolated('المشروعان YEP-2021-03، وWASH-2020-11؛')).toEqual([
      'YEP-2021-03',
      'WASH-2020-11',
    ]);
    expect(isolated('(انظر https://example.org/report_(final))')).toEqual([
      'https://example.org/report_(final)',
    ]);
  });

  it('isolates emails and file names', () => {
    expect(isolated('راسل info@example.org بخصوص annual-report-2021.pdf')).toEqual([
      'info@example.org',
      'annual-report-2021.pdf',
    ]);
  });

  it('leaves numbers alone: Arabic-Indic digits, Latin digits and ranges', () => {
    expect(isolated('بلغ عدد المستفيدين ١٢٠٠ شخص في 2019-2021 بنسبة 15%')).toEqual([]);
  });

  it('returns text without right-to-left characters as one plain segment', () => {
    const english = 'Funded through https://example.org/r under YEP-2021-03.';
    expect(splitBidi(english)).toEqual([{ text: english, isolate: false }]);
    expect(splitBidi('')).toEqual([]);
  });
});

describe('<Bidi>', () => {
  it('renders the fixture as a dir="auto" plaintext block with the runs in <bdi>', () => {
    const { container } = render(<Bidi as="p" text={FIXTURE} />);
    const block = container.firstElementChild as HTMLElement;

    expect(block.tagName).toBe('P');
    expect(block.getAttribute('dir')).toBe('auto');
    expect(block.className).toContain(styles.bidi);
    expect(block.textContent).toBe(FIXTURE);
    expect([...block.querySelectorAll('bdi')].map((el) => el.textContent)).toEqual([
      'YEP-2021-03',
      'https://example.org/r',
    ]);
    // Logical order: text, isolate, text, isolate, text. The browser does the visual order.
    expect([...block.childNodes].map((node) => node.nodeName)).toEqual([
      '#text',
      'BDI',
      '#text',
      'BDI',
      '#text',
    ]);
  });

  it('renders markup in content as text, never as HTML', () => {
    const { container } = render(<Bidi text={'نص <img src=x onerror=alert(1)> نص'} />);
    expect(container.querySelector('img')).toBeNull();
    expect(container.textContent).toBe('نص <img src=x onerror=alert(1)> نص');
  });

  it('defaults to an inline span and keeps extra classes', () => {
    const { container } = render(<Bidi text="Annual report" className="title" />);
    const block = container.firstElementChild as HTMLElement;
    expect(block.tagName).toBe('SPAN');
    expect(block.classList.contains('title')).toBe(true);
    expect(block.querySelector('bdi')).toBeNull();
  });
});
