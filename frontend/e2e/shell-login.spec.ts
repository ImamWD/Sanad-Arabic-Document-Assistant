// F1: login page. The auth endpoints (B2) are mocked with page.route; mocked requests still
// emit `request` events, so request counting stays meaningful.
import { expect, type Page, test } from '@playwright/test';

import ar from '../src/locales/ar.json' with { type: 'json' };
import en from '../src/locales/en.json' with { type: 'json' };

const VIEWER = {
  id: '00000000-0000-4000-8000-000000000001',
  name: 'ليلى تجريبية',
  email: 'viewer@example.org',
  role: 'viewer',
  preferred_language: 'ar',
  is_guest: false,
};
const GUEST = { ...VIEWER, name: 'ضيف تجريبي', email: '', is_guest: true };

const fail = (status: number, code: string) => ({
  status,
  json: { error: { code, params: {} } },
});

/** No session until a login or guest call succeeds. */
async function mockAuth(
  page: Page,
  login: { status: number; json: unknown } = { status: 200, json: VIEWER },
) {
  let user: unknown = null;
  await page.route('**/api/me', (route) =>
    route.fulfill(user ? { json: user } : fail(401, 'UNAUTHENTICATED')),
  );
  await page.route('**/api/auth/login', async (route) => {
    if (login.status === 200) user = login.json;
    await route.fulfill(login);
  });
  await page.route('**/api/auth/guest', async (route) => {
    user = GUEST;
    await route.fulfill({ json: GUEST });
  });
}

async function saveScreenshot(page: Page, name: string) {
  const info = test.info();
  const path = info.outputPath(`${name}.png`);
  await page.screenshot({ path, fullPage: true });
  await info.attach(name, { path, contentType: 'image/png' });
  // SHELL_SCREENSHOTS=1 refreshes the committed pair in e2e/__screenshots__/.
  if (process.env.SHELL_SCREENSHOTS)
    await page.screenshot({ path: `e2e/__screenshots__/${name}.png` });
}

for (const [lang, messages, dir] of [
  ['ar', ar, 'rtl'],
  ['en', en, 'ltr'],
] as const) {
  test(`login page in ${lang}: ${dir}, language switch visible before sign-in`, async ({
    page,
  }) => {
    await mockAuth(page);
    await page.goto(`/login?lang=${lang}`);
    await expect(page.locator('html')).toHaveAttribute('dir', dir);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(messages.app.title);
    await expect(page.getByRole('button', { name: messages.language.switch })).toBeVisible();
    await expect(page.getByLabel(messages.auth.login.email)).toBeVisible();
    await expect(page.getByLabel(messages.auth.login.password)).toBeVisible();
    await expect(page.getByRole('button', { name: messages.auth.login.guest })).toBeVisible();
    await saveScreenshot(page, `login-${lang}`);
  });
}

test('Enter in the password field signs in and lands on Ask', async ({ page }) => {
  await mockAuth(page);
  await page.goto('/?lang=ar');
  await expect(page).toHaveURL(/\/login/);

  await page.getByLabel(ar.auth.login.email).fill(VIEWER.email);
  await page.getByLabel(ar.auth.login.password).fill('not-a-real-password');
  const login = page.waitForRequest('**/api/auth/login');
  await page.getByLabel(ar.auth.login.password).press('Enter');

  const request = await login;
  expect(request.method()).toBe('POST');
  expect(request.postDataJSON()).toEqual({ email: VIEWER.email, password: 'not-a-real-password' });
  expect(request.headers()['x-sanad']).toBe('1');
  await expect(page).toHaveURL(/\/ask$/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(ar.pages.ask.title);
});

test('"Continue as guest" lands on Ask with viewer navigation', async ({ page }) => {
  await mockAuth(page);
  await page.goto('/login?lang=en');
  await page.getByRole('button', { name: en.auth.login.guest }).click();
  await expect(page).toHaveURL(/\/ask$/);
  const nav = page.getByRole('navigation', { name: en.shell.nav.label });
  await expect(nav.getByRole('link')).toHaveText([en.shell.nav.ask, en.shell.nav.library]);
});

test('a failed login shows the translated error code, never server prose', async ({ page }) => {
  await mockAuth(page, fail(401, 'INVALID_CREDENTIALS'));
  await page.goto('/login?lang=ar');
  await page.getByLabel(ar.auth.login.email).fill(VIEWER.email);
  await page.getByLabel(ar.auth.login.password).fill('wrong-password');
  await page.getByRole('button', { name: ar.auth.login.submit }).click();
  await expect(page.getByRole('alert')).toHaveText(ar.errors.INVALID_CREDENTIALS);
  await expect(page).toHaveURL(/\/login/);

  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ status: 500, json: { detail: 'Traceback (most recent call last)' } }),
  );
  await page.getByRole('button', { name: ar.auth.login.submit }).click();
  await expect(page.getByRole('alert')).toHaveText(ar.errors.UNKNOWN_ERROR);
  await expect(page.getByText(/Traceback/)).toHaveCount(0);
});

test('switching language on the login page makes no /api/* request', async ({ page }) => {
  await mockAuth(page);
  await page.goto('/login?lang=ar');
  await expect(page.getByLabel(ar.auth.login.email)).toBeVisible();

  const apiCalls: string[] = [];
  page.on('request', (req) => {
    if (new URL(req.url()).pathname.startsWith('/api/')) apiCalls.push(req.url());
  });
  await page.getByRole('button', { name: ar.language.switch }).click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
  await expect(page.getByLabel(en.auth.login.email)).toBeVisible();
  await page.getByRole('button', { name: en.language.switch }).click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  expect(apiCalls).toEqual([]);
});
