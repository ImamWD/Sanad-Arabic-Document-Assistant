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
  const apiCalls: string[] = [];
  page.on('request', (req) => {
    if (new URL(req.url()).pathname.startsWith('/api/')) apiCalls.push(req.url());
  });
  await page.goto('/?lang=ar');
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
