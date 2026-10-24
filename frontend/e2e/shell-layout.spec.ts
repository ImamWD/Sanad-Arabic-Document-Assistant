// F1: the signed-in shell. /api/me is mocked per role (B2 provides the real endpoint).
import { expect, type Page, test } from '@playwright/test';

import ar from '../src/locales/ar.json' with { type: 'json' };
import en from '../src/locales/en.json' with { type: 'json' };

type Role = 'viewer' | 'editor' | 'admin';

const USERS = {
  viewer: { id: '00000000-0000-4000-8000-000000000001', name: 'ليلى تجريبية' },
  editor: { id: '00000000-0000-4000-8000-000000000002', name: 'Sami Example' },
  admin: { id: '00000000-0000-4000-8000-000000000003', name: 'مدير تجريبي' },
} as const;

function user(role: Role) {
  return {
    ...USERS[role],
    email: `${role}@example.org`,
    role,
    preferred_language: 'ar',
    is_guest: false,
  };
}

/** GET /api/me answers with the user; PATCH /api/me (the saved language) is accepted. */
async function signIn(page: Page, role: Role) {
  await page.route('**/api/me', (route) =>
    route.request().method() === 'PATCH'
      ? route.fulfill({ status: 204 })
      : route.fulfill({ json: user(role) }),
  );
  await page.route('**/api/auth/logout', (route) => route.fulfill({ status: 204 }));
}

/** Console errors and CSP violations (a blocked inline style would show up here). */
function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', (err) => errors.push(err.message));
  return errors;
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

const NAV = {
  viewer: ['ask', 'library'],
  editor: ['ask', 'library', 'upload'],
  admin: ['ask', 'library', 'upload', 'admin'],
} as const;

for (const role of ['viewer', 'editor', 'admin'] as const) {
  test(`${role} navigation`, async ({ page }) => {
    await signIn(page, role);
    await page.goto('/ask?lang=en');
    const nav = page.getByRole('navigation', { name: en.shell.nav.label });
    await expect(nav.getByRole('link')).toHaveText(NAV[role].map((id) => en.shell.nav[id]));
  });
}

test('a viewer who opens /admin is told they have no access', async ({ page }) => {
  await signIn(page, 'viewer');
  await page.goto('/admin?lang=ar');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(ar.pages.forbidden.title);
});

for (const [lang, messages, dir] of [
  ['ar', ar, 'rtl'],
  ['en', en, 'ltr'],
] as const) {
  test(`the shell is laid out ${dir} in ${lang}`, async ({ page }) => {
    const errors = watchErrors(page);
    await signIn(page, 'admin');
    await page.goto(`/ask?lang=${lang}`);
    await expect(page.locator('html')).toHaveAttribute('dir', dir);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(messages.pages.ask.title);

    // Navigation at the inline start: right of the content in Arabic, left in English.
    const nav = await page
      .getByRole('navigation', { name: messages.shell.nav.label })
      .boundingBox();
    const main = await page.getByRole('main').boundingBox();
    const brand = await page.getByRole('link', { name: messages.app.name }).boundingBox();
    const menu = await page.getByRole('button', { name: USERS.admin.name }).boundingBox();
    if (!nav || !main || !brand || !menu) throw new Error('shell not rendered');
    if (dir === 'rtl') {
      expect(nav.x).toBeGreaterThan(main.x);
      expect(brand.x).toBeGreaterThan(menu.x);
    } else {
      expect(nav.x).toBeLessThan(main.x);
      expect(brand.x).toBeLessThan(menu.x);
    }
    await saveScreenshot(page, `shell-${lang}`);

    // The user menu opens under its trigger, aligned to the inline end, and stays on screen.
    await page.getByRole('button', { name: USERS.admin.name }).click();
    const content = await page.getByRole('menu').boundingBox();
    if (!content) throw new Error('menu not open');
    if (dir === 'rtl') expect(Math.round(content.x)).toBeLessThanOrEqual(Math.round(menu.x));
    else expect(content.x + content.width).toBeGreaterThanOrEqual(menu.x + menu.width - 1);
    await expect(page.getByRole('menu')).toHaveAttribute('dir', dir);
    await saveScreenshot(page, `shell-menu-${lang}`);

    expect(errors).toEqual([]);
  });
}

test('directional icons mirror in Arabic; others never do', async ({ page }) => {
  await signIn(page, 'viewer');
  const transform = (icon: string) =>
    page
      .locator(`svg[data-icon="${icon}"]`)
      .first()
      .evaluate((el) => getComputedStyle(el).transform);

  await page.goto('/ask?lang=ar');
  await page.getByRole('button', { name: USERS.viewer.name }).click();
  expect(await transform('signOut')).toBe('matrix(-1, 0, 0, 1, 0, 0)');
  expect(await transform('globe')).toBe('none');

  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: ar.language.switch }).click();
  await page.getByRole('button', { name: USERS.viewer.name }).click();
  expect(await transform('signOut')).toBe('none');
  expect(await transform('globe')).toBe('none');
});

test('switching language in the shell makes no GET, keeps the page, and saves the choice', async ({
  page,
}) => {
  await signIn(page, 'editor');
  await page.goto('/library?lang=ar');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(ar.pages.library.title);

  const gets: string[] = [];
  const saved: unknown[] = [];
  page.on('request', (req) => {
    if (!new URL(req.url()).pathname.startsWith('/api/')) return;
    if (req.method() === 'GET') gets.push(req.url());
    else if (req.method() === 'PATCH') saved.push(req.postDataJSON());
  });
  await page.getByRole('button', { name: ar.language.switch }).click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
  await expect(page).toHaveURL(/\/library/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(en.pages.library.title);
  await page.getByRole('link', { name: en.shell.nav.ask }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(en.pages.ask.title);
  await page.getByRole('button', { name: en.language.switch }).click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');

  expect(gets).toEqual([]);
  await expect
    .poll(() => saved)
    .toEqual([{ preferred_language: 'en' }, { preferred_language: 'ar' }]);
});

test("a signed-in user's saved language applies when no language was picked", async ({ page }) => {
  await signIn(page, 'viewer'); // preferred_language: ar
  await page.goto('/ask');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(ar.pages.ask.title);
});

test('signing out returns to the login page', async ({ page }) => {
  await signIn(page, 'viewer');
  await page.goto('/ask?lang=en');
  await page.getByRole('button', { name: USERS.viewer.name }).click();
  const logout = page.waitForRequest('**/api/auth/logout');
  await page.getByRole('menuitem', { name: en.shell.user.signOut }).click();
  expect((await logout).headers()['x-sanad']).toBe('1');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('button', { name: en.auth.login.submit })).toBeVisible();
});
