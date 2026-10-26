// F2: the Ask screen while an answer is on its way (SYSTEM_DESIGN §6, client requirement:
// never looks frozen). The stream is fed one event at a time; see ask-mock.ts.
import { expect, type Page, test } from '@playwright/test';

import ar from '../src/locales/ar.json' with { type: 'json' };
import en from '../src/locales/en.json' with { type: 'json' };
import {
  ANSWER,
  ask,
  controlStream,
  FINAL_GATE,
  FINAL_LOW_CONFIDENCE,
  FINAL_SENTINEL,
  QUESTION,
  signIn,
  VIEWER,
} from './ask-mock';

async function saveScreenshot(page: Page, name: string) {
  const info = test.info();
  const path = info.outputPath(`${name}.png`);
  await page.screenshot({ path, fullPage: true });
  await info.attach(name, { path, contentType: 'image/png' });
}

const fill = (template: string, values: Record<string, string>) =>
  template.replace(/\{\{(\w+)\}\}/g, (_, name: string) => values[name] ?? '');

test('the stage is said in words within a second, then each stage follows', async ({ page }) => {
  await signIn(page);
  const stream = await controlStream(page);
  await page.goto('/ask?lang=en');
  await ask(page, en.ask.form.label);

  const status = page.getByRole('status');
  await expect(status).toContainText(en.ask.stage.starting, { timeout: 1000 });
  expect(await stream.requests()).toEqual([
    expect.objectContaining({ body: JSON.stringify({ question: QUESTION }) }),
  ]);
  expect((await stream.requests())[0]?.headers['x-sanad']).toBe('1');

  await stream.send('stage', { stage: 'searching' });
  await expect(status).toContainText(en.ask.stage.searching, { timeout: 1000 });
  await stream.send('stage', { stage: 'reading', sources: 6, band: 'answer' });
  await expect(status).toContainText(en.ask.stage.reading);
  await expect(status).toContainText(fill(en.ask.detail.reading, { sources: '6' }));
  await stream.send('stage', { stage: 'queued', position: 2 });
  await expect(status).toContainText(fill(en.ask.detail.queued, { position: '2' }));
});

test('an estimate of 20 seconds or less gets no notice, only the counter', async ({ page }) => {
  await signIn(page);
  const stream = await controlStream(page);
  await page.goto('/ask?lang=en');
  await ask(page, en.ask.form.label);
  await stream.send('stage', { stage: 'reading', sources: 4, band: 'answer' });
  await stream.send('eta', { expected_seconds: 20 });

  await expect(page.getByText(/of about 20 seconds/)).toBeVisible();
  await expect(page.getByText(/may take about/)).toHaveCount(0);
});

test('above 20 seconds the notice comes before writing, then the overrun message', async ({
  page,
}) => {
  await page.clock.install();
  await signIn(page);
  const stream = await controlStream(page);
  await page.goto('/ask?lang=en');
  await ask(page, en.ask.form.label);
  await stream.send('stage', { stage: 'reading', sources: 4, band: 'answer' });
  await stream.send('eta', { expected_seconds: 24 });

  const status = page.getByRole('status');
  await expect(status).toContainText(fill(en.ask.wait.notice, { duration: '24 seconds' }));
  await expect(status).not.toContainText(en.ask.stage.writing);
  await expect(page.getByText(/of about 24 seconds/)).toBeVisible();
  await saveScreenshot(page, 'ask-wait-notice-en');

  // Past 1.25 × 24 = 30 seconds without a token, the counter says so.
  await page.clock.fastForward(31_000);
  await expect(page.getByText(/taking longer than usual/)).toBeVisible();
  await expect(page.getByText(/of about 24 seconds/)).toHaveCount(0);
  await saveScreenshot(page, 'ask-wait-overrun-en');

  await stream.send('stage', { stage: 'writing' });
  await stream.send('token', { text: 'In 2021 the programme' });
  await expect(status).toContainText(en.ask.stage.writing);
  await expect(page.getByText('In 2021 the programme')).toBeVisible();
  await expect(page.getByText(/taking longer than usual/)).toHaveCount(0);
  await expect(page.getByText(/may take about/)).toHaveCount(0);
});

for (const [lang, messages, dir] of [
  ['en', en, 'ltr'],
  ['ar', ar, 'rtl'],
] as const) {
  test(`the amber banner shows before the first token (${lang}, ${dir})`, async ({ page }) => {
    await signIn(page);
    const stream = await controlStream(page);
    await page.goto(`/ask?lang=${lang}`);
    await expect(page.locator('html')).toHaveAttribute('dir', dir);
    await ask(page, messages.ask.form.label);
    await stream.send('stage', { stage: 'reading', sources: 3, band: 'low_confidence' });

    const banner = page.getByRole('note');
    await expect(banner).toHaveText(messages.answer.lowConfidence);
    await expect(page.getByRole('article').locator('p[dir]')).toHaveCount(0);

    await stream.send('eta', { expected_seconds: 45 });
    await stream.send('token', { text: 'In 2021 the programme' });
    await expect(page.getByText('In 2021 the programme')).toBeVisible();
    await expect(banner).toBeVisible();
    await saveScreenshot(page, `ask-streaming-low-confidence-${lang}`);

    await stream.send('final', FINAL_LOW_CONFIDENCE);
    await expect(page.getByText(ANSWER, { exact: true })).toBeVisible();
    await expect(banner).toHaveText(messages.answer.lowConfidence);
  });
}

test('a refusal replaces the streamed text and says why: gate versus sentinel', async ({
  page,
}) => {
  await signIn(page, VIEWER);
  const stream = await controlStream(page);
  await page.goto('/ask?lang=en');

  await ask(page, en.ask.form.label);
  await stream.send('token', { text: 'The enrolment figure was' });
  await expect(page.getByText('The enrolment figure was')).toBeVisible();
  await stream.send('final', FINAL_GATE);
  await expect(page.getByText('The enrolment figure was')).toHaveCount(0);
  await expect(page.getByText(en.answer.refusal)).toBeVisible();
  await expect(page.getByText(en.ask.refusal.gate)).toBeVisible();
  await expect(
    page.getByRole('list', { name: en.ask.refusal.nearest }).getByRole('link'),
  ).toHaveCount(3);
  await saveScreenshot(page, 'ask-refusal-gate-en');

  await ask(page, en.ask.form.label, 'Which donor funded the 2015 water project?');
  await stream.send('stage', { stage: 'writing' });
  await stream.send('token', { text: 'The donor was' });
  await expect(page.getByText('The donor was')).toBeVisible();
  await stream.send('final', FINAL_SENTINEL);
  await expect(page.getByText('The donor was')).toHaveCount(0);
  await expect(page.getByText(en.answer.refusal)).toBeVisible();
  await expect(page.getByText(en.ask.refusal.read)).toBeVisible();
  await expect(page.getByText(en.ask.refusal.gate)).toHaveCount(0);
  expect(en.ask.refusal.read).not.toBe(en.ask.refusal.gate);
});

test('an error event removes the streamed text and shows the translated code', async ({ page }) => {
  await signIn(page);
  const stream = await controlStream(page);
  await page.goto('/ask?lang=ar');
  await ask(page, ar.ask.form.label, 'كم عدد الفتيات المسجلات في عام 2021؟');
  await stream.send('token', { text: 'بلغ عدد' });
  await expect(page.getByText('بلغ عدد')).toBeVisible();
  await stream.send('error', { error: { code: 'INTERNAL_ERROR', params: {} } });
  await expect(page.getByRole('alert')).toHaveText(ar.errors.INTERNAL_ERROR);
  await expect(page.getByText('بلغ عدد')).toHaveCount(0);
  await expect(page.getByRole('button', { name: ar.ask.retry })).toBeVisible();
});
