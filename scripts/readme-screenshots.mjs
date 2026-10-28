// The README screenshots, taken from the running stack as the guest (nothing mocked).
//
//   make up
//   docker compose run --rm -T e2e node --input-type=module - < scripts/readme-screenshots.mjs
//
// It writes PNGs to frontend/.shots/ (git-ignored; the e2e container mounts only frontend/).
// Copy the ones the README uses into docs/assets/. The answers come from the configured model,
// so a CPU stack needs a few minutes for the three questions.
import fs from 'node:fs';
import { chromium } from '@playwright/test';

const base = process.env.E2E_BASE_URL;
const out = '/app/frontend/.shots';
fs.mkdirSync(out, { recursive: true });
const en = JSON.parse(fs.readFileSync('/app/frontend/src/locales/en.json', 'utf8'));
const ar = JSON.parse(fs.readFileSync('/app/frontend/src/locales/ar.json', 'utf8'));

// Dev set D08, D03 and D35 (eval/dev_questions.yaml): never the headline questions.
const EN_Q =
  'While schools were shut in 2020, roughly how many girls kept up their studies by following the radio broadcasts?';
const AR_Q = 'كم من الوقت كانت تستغرق رحلة إحضار الماء في قرى الهضبة الشرقية قبل بدء مشروع المياه؟';
const NO_ANSWER_Q = 'شو بتعرفني عن برنامج التمويل الأصغر تبع المؤسسة؟';

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
const shot = async (name) => {
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${out}/${name}.png` });
  console.log('saved', name);
};
const ask = async (label, q) => {
  const box = page.getByRole('textbox', { name: label });
  await box.fill(q);
  await box.press('Enter');
};
const cards = () => page.getByRole('link').filter({ hasText: /Page \d+|صفحة|الصفحة/ });

// The viewer scrolls to the cited page; scroll back a little so the toolbar shows.
const viewerShot = async (name) => {
  await page.locator('[aria-current="true"][data-rendered="true"]').first().waitFor({ timeout: 60_000 });
  await page.waitForTimeout(800);
  await page.evaluate(() => window.scrollBy(0, -320));
  await shot(name);
};
// The new question's heading first, then no progress bar and either citations or a refusal.
const waitAnswer = async (q) => {
  await page.waitForFunction((t) => document.querySelector('h2')?.textContent?.includes(t), q, { timeout: 30_000 });
  await page.waitForFunction(
    () =>
      !document.querySelector('[role="progressbar"]') &&
      (document.querySelectorAll('a[href^="/documents/"]').length > 0 ||
        /لا تتناول|قُرئت بعض|did not|not covered|No answer/i.test(document.querySelector('main')?.innerText ?? '')),
    null,
    { timeout: 240_000 },
  );
};

await page.goto(`${base}/login?lang=en`);
await shot('01-login-en');
await page.getByRole('button', { name: en.auth.login.guest }).click();

await ask(en.ask.form.label, EN_Q);
await waitAnswer(EN_Q);
await shot('02-answer-en');
await cards().first().click();
await viewerShot('03-viewer-en');

// Asked again (the model's prompt cache answers fast), then the language switch.
await page.goto(`${base}/ask`);
await ask(en.ask.form.label, EN_Q);
await waitAnswer(EN_Q);
await page.getByRole('button', { name: en.language.switch }).click();
await page.waitForFunction(() => document.documentElement.dir === 'rtl');
await shot('04-same-answer-ar-ui');
await cards().first().click();
await viewerShot('05-viewer-ar-ui');

await page.goto(`${base}/ask`);
await ask(ar.ask.form.label, AR_Q);
await waitAnswer(AR_Q);
await shot('06-answer-ar');

await ask(ar.ask.form.label, NO_ANSWER_Q);
await waitAnswer(NO_ANSWER_Q);
await shot('07-refusal-ar');

await page.goto(`${base}/library`);
await page.locator('table tbody tr').first().waitFor({ timeout: 30_000 });
await shot('08-library-ar');
await page.getByRole('button', { name: ar.language.switch }).click();
await page.waitForFunction(() => document.documentElement.dir === 'ltr');
await shot('09-library-en');

await browser.close();
