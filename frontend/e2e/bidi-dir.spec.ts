// Content takes the direction of its first strong character, even when that character sits in
// a run <Bidi> isolates in <bdi> (dir="auto" skips <bdi> content, so it would pick the Arabic).
import { expect, type Locator, test } from '@playwright/test';

import ar from '../src/locales/ar.json' with { type: 'json' };
import en from '../src/locales/en.json' with { type: 'json' };
import { ask, FINAL_ANSWERED, mockFullStream, signIn } from './ask-mock';
import { makeDoc, mockLibrary, signInAs } from './library-mock';

// The owner's repro on the Ask screen.
const QUESTION = "could you tell me about 'نظام الصحة المجتمعية'?";

/** The element's resolved direction, and where its first and last characters land. */
async function layout(block: Locator) {
  return block.evaluate((el) => {
    const range = document.createRange();
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const nodes: Text[] = [];
    while (walker.nextNode()) nodes.push(walker.currentNode as Text);
    const first = nodes.at(0);
    const last = nodes.at(-1);
    if (!first || !last) return null;
    range.setStart(first, 0);
    range.setEnd(first, 1);
    const start = range.getBoundingClientRect().x;
    range.setStart(last, last.length - 1);
    range.setEnd(last, last.length);
    const end = range.getBoundingClientRect().x;
    return { direction: getComputedStyle(el).direction, start, end };
  });
}

for (const [lang, messages] of [
  ['en', en],
  ['ar', ar],
] as const) {
  test(`an English-first question is laid out left to right (${lang} UI)`, async ({ page }) => {
    await signIn(page);
    await mockFullStream(page, [['final', FINAL_ANSWERED]]);
    await page.goto(`/ask?lang=${lang}`);
    await ask(page, messages.ask.form.label, QUESTION);

    const heading = page.getByRole('heading', { level: 2, name: QUESTION });
    await expect(heading).toHaveAttribute('dir', 'ltr');
    const box = await layout(heading);
    expect(box?.direction).toBe('ltr');
    // "c" opens the line on the left and "?" closes it on the right.
    expect(box && box.start < box.end).toBe(true);
  });
}

test('an Arabic-first title with a code stays right to left in the English UI', async ({
  page,
}) => {
  const doc = makeDoc({ title: 'محضر اجتماع مجلس الإدارة للمشروع YEP-2021-03' });
  await signInAs(page, 'viewer');
  await mockLibrary(page, { role: 'viewer', documents: [doc] });
  await page.goto('/library?lang=en');
  const title = page.locator(`tr[data-document-id="${doc.id}"] a span[dir]`);
  await expect(title).toHaveAttribute('dir', 'rtl');
  const box = await layout(title);
  expect(box?.direction).toBe('rtl');
  // "م" opens the line on the right; the code, last in reading order, ends on the left.
  expect(box && box.start > box.end).toBe(true);
  await expect(title.locator('bdi')).toHaveText('YEP-2021-03');
});
