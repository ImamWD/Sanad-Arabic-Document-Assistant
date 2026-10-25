// End-to-end smoke test on the full stack, nothing mocked: guest login, a question, the first
// citation, the viewer at the cited page, in at most two clicks after login.
//
// Needs the real ask pipeline (R1) and documents API (B3) with the seed corpus indexed, so it
// is skipped unless SANAD_FULL_STACK is set. Run it with:
//   make up
//   docker compose run --rm -e SANAD_FULL_STACK=1 e2e npx playwright test smoke.spec.ts
// (inside a git worktree, export SANAD_INSTANCE and WEB_PORT as `make info` prints them first).
import { expect, test } from '@playwright/test';

import en from '../src/locales/en.json' with { type: 'json' };

test.skip(!process.env.SANAD_FULL_STACK, 'needs the full stack: set SANAD_FULL_STACK=1');

// Dev set D08 (eval/dev_questions.yaml), answered by the GEP mid-term evaluation. The test
// never assumes which page is cited: it checks the viewer against the citation it clicked.
const QUESTION =
  'While schools were shut in 2020, roughly how many girls kept up their studies by following the radio broadcasts?';

test('guest: question, first citation, cited page in the viewer', async ({ page }) => {
  // A CPU-only local model can take a while to answer.
  test.setTimeout(240_000);
  await page.goto('/login?lang=en');

  await page.getByRole('button', { name: en.auth.login.guest }).click(); // login
  const box = page.getByRole('textbox', { name: en.ask.form.label });
  await box.fill(QUESTION);
  await box.press('Enter'); // Enter sends: no click

  const cards = page.getByRole('link').filter({ hasText: /Page \d+/ });
  await expect(cards.first()).toBeVisible({ timeout: 200_000 });
  const href = (await cards.first().getAttribute('href')) ?? '';
  const match = /^\/documents\/([^?]+)\?page=(\d+)$/.exec(href);
  if (!match) throw new Error(`not a viewer link: ${href}`);
  const [, documentId, citedPage] = match.map(String);

  await cards.first().click(); // click 1 after login

  await expect(page).toHaveURL(new RegExp(`/documents/${documentId}\\?page=${citedPage}$`));
  const cited = page.getByRole('group', { name: `Page ${citedPage}`, exact: true });
  await expect(cited).toHaveAttribute('aria-current', 'true', { timeout: 30_000 });
  await expect(cited).toHaveAttribute('data-rendered', 'true');
  await expect(cited).toBeInViewport();
});
