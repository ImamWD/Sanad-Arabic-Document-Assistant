import { expect, test } from '@playwright/test';

import ar from '../src/locales/ar.json' with { type: 'json' };
import en from '../src/locales/en.json' with { type: 'json' };

test('?lang=ar renders right-to-left Arabic', async ({ page }) => {
  await page.goto('/?lang=ar');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.locator('html')).toHaveAttribute('lang', 'ar');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(ar.app.title);
  await expect(page).toHaveTitle(ar.app.title);
});

test('?lang=en renders left-to-right English', async ({ page }) => {
  await page.goto('/?lang=en');
  await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(en.app.title);
});

test('switching language mirrors the page without calling the API', async ({ page }) => {
  // Record only after the page has rendered and the boot session check (GET /api/me, F1) has
  // settled: the switch itself must make no request.
  const sessionCheck = page.waitForResponse((res) => new URL(res.url()).pathname === '/api/me');
  await page.goto('/?lang=ar');
  await sessionCheck;
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(ar.app.title);

  const apiCalls: string[] = [];
  page.on('request', (req) => {
    if (new URL(req.url()).pathname.startsWith('/api/')) apiCalls.push(req.url());
  });
  await page.getByRole('button', { name: ar.language.switch }).click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  expect(apiCalls).toEqual([]);
});

test('the Arabic font is self-hosted and nothing loads from another origin', async ({
  page,
  baseURL,
}) => {
  const origin = new URL(baseURL ?? '').origin;
  const foreign: string[] = [];
  const fonts: string[] = [];
  page.on('request', (req) => {
    const url = new URL(req.url());
    if (url.origin !== origin) foreign.push(req.url());
    else if (url.pathname.endsWith('.woff2')) fonts.push(url.pathname);
  });
  await page.goto('/?lang=ar');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  const faces = await page.evaluate(
    async () => (await document.fonts.load('600 24px "IBM Plex Sans Arabic"', 'سند')).length,
  );
  expect(faces).toBeGreaterThan(0);
  expect(fonts.some((path) => path.startsWith('/assets/'))).toBe(true);
  expect(foreign).toEqual([]);
});

test("the guest's language choice survives a reload, whatever the shared account says", async ({
  page,
}) => {
  // The guest can't save a language to its account (a shared one), so its choice lives in
  // this browser: ?lang=, then localStorage, then English; the account's language never wins.
  const guest = {
    id: '00000000-0000-4000-8000-000000000009',
    name: 'ضيف تجريبي',
    email: '',
    role: 'viewer',
    preferred_language: 'en',
    is_guest: true,
  };
  const saved: unknown[] = [];
  await page.route('**/api/me', (route) => {
    if (route.request().method() === 'PATCH') {
      saved.push(route.request().postDataJSON());
      return route.fulfill({ status: 204 });
    }
    return route.fulfill({ json: guest });
  });
  await page.goto('/ask?lang=en');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await page.getByRole('button', { name: en.language.switch }).click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');

  await page.goto('/ask');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(ar.pages.ask.title);
  await expect(page.locator('html')).toHaveAttribute('lang', 'ar');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang', 'ar');
  expect(saved).toEqual([]);
});
