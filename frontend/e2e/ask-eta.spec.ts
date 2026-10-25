// The wait estimate in words: minutes from 90 seconds up, and no number at all when the server
// is busy (R1d marks a capped estimate with `capped: true`). The stream is mocked (ask-mock.ts).
import { expect, test } from '@playwright/test';

import ar from '../src/locales/ar.json' with { type: 'json' };
import en from '../src/locales/en.json' with { type: 'json' };
import { ask, controlStream, signIn } from './ask-mock';

for (const [lang, messages] of [
  ['en', en],
  ['ar', ar],
] as const) {
  test(`a capped estimate says the server is busy, with no number (${lang})`, async ({ page }) => {
    await page.clock.install();
    await signIn(page);
    const stream = await controlStream(page);
    await page.goto(`/ask?lang=${lang}`);
    await ask(page, messages.ask.form.label);
    await stream.send('stage', { stage: 'reading', sources: 4, band: 'answer' });
    await stream.send('eta', { expected_seconds: 600, capped: true });

    // The busy notice names no duration. (The status line still counts the sources found.)
    const status = page.getByRole('status');
    await expect(status.getByText(messages.ask.wait.busy, { exact: true })).toBeVisible();
    await expect(status).not.toContainText('600');
    // An indeterminate bar: no max and no value, so it promises no end.
    const bar = page.getByRole('progressbar');
    await expect(bar).not.toHaveAttribute('max');
    await expect(bar).not.toHaveAttribute('value');

    // Two minutes in, the counter says minutes and still names no end.
    await page.clock.runFor(125_000);
    const elapsed = lang === 'en' ? '2 minutes' : 'دقيقتان';
    await expect(
      page.getByText(messages.ask.wait.elapsedOnly.replace('{{elapsed}}', elapsed)),
    ).toBeVisible();
  });
}

test('an estimate over 90 seconds is said in minutes', async ({ page }) => {
  await signIn(page);
  const stream = await controlStream(page);
  await page.goto('/ask?lang=en');
  await ask(page, en.ask.form.label);
  await stream.send('stage', { stage: 'reading', sources: 4, band: 'answer' });
  await stream.send('eta', { expected_seconds: 300 });

  await expect(page.getByRole('status')).toContainText(
    en.ask.wait.notice.replace('{{duration}}', '5 minutes'),
  );
  await expect(page.getByText(/seconds of about 5 minutes/)).toBeVisible();
  await expect(page.getByRole('progressbar')).toHaveAttribute('max', '300');
});
