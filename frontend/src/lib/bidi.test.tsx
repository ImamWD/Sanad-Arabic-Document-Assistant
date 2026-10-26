import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { Bidi } from './BidiText';
import { baseDirection, splitBidi } from './bidi';
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

describe('baseDirection', () => {
  it('follows the first strong character, even when it sits in a run that gets isolated', () => {
    expect(baseDirection("could you tell me about 'نظام الصحة المجتمعية'?")).toBe('ltr');
    expect(baseDirection(FIXTURE)).toBe('rtl');
    expect(baseDirection('«WASH-2018-01» مشروع')).toBe('ltr');
    expect(baseDirection('(١٢) تقرير')).toBe('rtl');
  });

  it('has no answer for text without letters', () => {
    expect(baseDirection('2019-2021, ١٢٠٠ (15%)')).toBeNull();
    expect(baseDirection('')).toBeNull();
  });
});

describe('<Bidi>', () => {
  it('renders the fixture as an rtl block with the runs in <bdi>', () => {
    const { container } = render(<Bidi as="p" text={FIXTURE} />);
    const block = container.firstElementChild as HTMLElement;

    expect(block.tagName).toBe('P');
    expect(block.getAttribute('dir')).toBe('rtl');
    expect(block.className).toContain(styles.bidi);
    expect(block.className).toContain(styles.known);
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

  it('gives an English-first sentence ltr, though its first run is isolated in <bdi>', () => {
    const question = "could you tell me about 'نظام الصحة المجتمعية'?";
    const { container } = render(<Bidi as="h2" text={question} />);
    const block = container.firstElementChild as HTMLElement;
    expect(block.getAttribute('dir')).toBe('ltr');
    expect(block.classList.contains(styles.known ?? '')).toBe(true);
    expect(block.querySelector('bdi')?.textContent).toBe('could you tell me about');
    expect(block.textContent).toBe(question);
  });

  it('gives an Arabic-first sentence with an English code rtl', () => {
    const { container } = render(<Bidi text="محضر الاجتماع للمشروع YEP-2021-03" />);
    const block = container.firstElementChild as HTMLElement;
    expect(block.getAttribute('dir')).toBe('rtl');
    expect(block.querySelector('bdi')?.textContent).toBe('YEP-2021-03');
  });

  it('leaves text without letters to dir="auto"', () => {
    const { container } = render(<Bidi text="2019-2021: ١٢٠٠" />);
    const block = container.firstElementChild as HTMLElement;
    expect(block.getAttribute('dir')).toBe('auto');
    expect(block.classList.contains(styles.known ?? '')).toBe(false);
  });

  it('never wraps inside a code, so "WASH-2018-01" stays whole and in order', () => {
    const { container } = render(
      <Bidi text="التقييم النهائي لمشروع المياه في قرى الهضبة الشرقية (WASH-2018-01)" />,
    );
    const code = container.querySelector('bdi');
    expect(code?.textContent).toBe('WASH-2018-01');
    expect(code?.classList.contains(styles.nowrap ?? '')).toBe(true);
    expect(code?.children).toHaveLength(0);
  });

  it('lets a URL wrap only after a slash', () => {
    const { container } = render(<Bidi text={FIXTURE} />);
    const url = container.querySelectorAll('bdi')[1];
    expect(url?.textContent).toBe('https://example.org/r');
    const pieces = [...(url?.querySelectorAll('span') ?? [])];
    expect(pieces.map((el) => el.textContent)).toEqual(['https:/', '/', 'example.org/', 'r']);
    expect(pieces.every((el) => el.classList.contains(styles.nowrap ?? ''))).toBe(true);
    // A break opportunity between the pieces, and nowhere else.
    expect([...(url?.childNodes ?? [])].map((node) => node.nodeName)).toEqual([
      'SPAN',
      'WBR',
      'SPAN',
      'WBR',
      'SPAN',
      'WBR',
      'SPAN',
    ]);
  });

  it('lets an English phrase wrap only between its words', () => {
    const { container } = render(<Bidi text="قدّم برنامج Youth Employment-Plus Programme دعمًا" />);
    const phrase = container.querySelector('bdi');
    expect(phrase?.textContent).toBe('Youth Employment-Plus Programme');
    expect(phrase?.classList.contains(styles.nowrap ?? '')).toBe(false);
    const words = [...(phrase?.querySelectorAll('span') ?? [])];
    expect(words.map((el) => el.textContent)).toEqual(['Youth', 'Employment-Plus', 'Programme']);
    expect(words.every((el) => el.classList.contains(styles.nowrap ?? ''))).toBe(true);
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
    expect(block.getAttribute('dir')).toBe('ltr');
    expect(block.classList.contains('title')).toBe(true);
    expect(block.querySelector('bdi')).toBeNull();
  });
});
