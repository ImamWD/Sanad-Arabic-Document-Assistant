// F5: Admin users and roles, against the real stack (B2's /api/admin/users and the demo
// accounts). The database persists between runs and accounts are never deleted, so each run
// creates its own obviously fake account, and only that account is ever deactivated.
import { expect, type Locator, type Page, test } from '@playwright/test';

import ar from '../src/locales/ar.json' with { type: 'json' };
import en from '../src/locales/en.json' with { type: 'json' };

type Messages = typeof en;

// The demo passwords (DEMO_*_PASSWORD in .env.example); override them to match the stack.
const DEMO = {
  admin: {
    email: 'admin@sanad.example',
    password: process.env.DEMO_ADMIN_PASSWORD ?? 'admin-demo-2026',
  },
  viewer: {
    email: 'viewer@sanad.example',
    password: process.env.DEMO_VIEWER_PASSWORD ?? 'viewer-demo-2026',
  },
};
const GUEST_EMAIL = 'guest@sanad.example';
const PASSWORD = 'e2e-password-2026';

/**
 * Sign in through the API, not the login form: signing in on the form with ?lang= would save
 * that language to the shared demo account's profile.
 */
async function signIn(page: Page, who: keyof typeof DEMO) {
  const response = await page.request.post('/api/auth/login', {
    headers: { 'X-Sanad': '1' },
    data: DEMO[who],
  });
  expect(response.status()).toBe(200);
}

/** Open /admin in `lang` and wait for the users table. */
async function openAdmin(page: Page, lang: 'ar' | 'en' = 'en') {
  const messages: Messages = lang === 'ar' ? ar : en;
  const list = page.waitForResponse(
    (res) => new URL(res.url()).pathname === '/api/admin/users' && res.status() === 200,
  );
  await page.goto(`/admin?lang=${lang}`);
  await list;
  await expect(page.getByRole('table', { name: messages.admin.users.heading })).toBeVisible();
  return messages;
}

const rowOf = (page: Page, email: string) => page.getByRole('row').filter({ hasText: email });

async function openEditor(page: Page, email: string, messages: Messages = en): Promise<Locator> {
  await rowOf(page, email).getByRole('button', { name: messages.admin.users.edit }).click();
  const form = page.getByRole('form', { name: messages.admin.users.edit });
  await expect(form).toBeVisible();
  return form;
}

const field = (scope: Locator, label: string) => scope.getByLabel(label, { exact: true });

test.beforeEach(async ({ page }) => {
  await signIn(page, 'admin');
});

test('the admin creates a user, changes the role, deactivates and reactivates them', async ({
  page,
  request,
}) => {
  const stamp = Date.now().toString(36);
  const user = { name: `Hala Example ${stamp}`, email: `hala.e2e.${stamp}@sanad.example` };
  const signInAsUser = () =>
    request.post('/api/auth/login', {
      headers: { 'X-Sanad': '1' },
      data: { email: user.email, password: PASSWORD },
    });
  await openAdmin(page);

  // Create.
  await page.getByRole('button', { name: en.admin.create.open }).click();
  const create = page.getByRole('form', { name: en.admin.create.heading });
  await field(create, en.admin.fields.name).fill(user.name);
  await field(create, en.admin.fields.email).fill(user.email);
  await field(create, en.admin.fields.password).fill(PASSWORD);
  await field(create, en.admin.fields.language).selectOption('ar');
  const post = page.waitForRequest(
    (req) => req.method() === 'POST' && new URL(req.url()).pathname === '/api/admin/users',
  );
  await create.getByRole('button', { name: en.admin.create.submit }).click();
  expect((await post).headers()['x-sanad']).toBe('1');
  await expect(page.getByRole('status')).toHaveText(en.admin.notice.created);
  const row = rowOf(page, user.email);
  await expect(row).toContainText(user.name);
  await expect(row).toContainText(en.roles.viewer);
  await expect(row).toContainText(en.admin.languages.ar);
  await expect(row).toContainText(en.admin.users.active);
  await expect(row).toContainText(en.admin.users.never);

  // Change the role.
  let form = await openEditor(page, user.email);
  await field(form, en.admin.fields.role).selectOption('editor');
  await form.getByRole('button', { name: en.admin.edit.save }).click();
  await expect(page.getByRole('status')).toHaveText(en.admin.notice.saved);
  await expect(row).toContainText(en.roles.editor);

  // Deactivate: nothing is sent until the admin confirms.
  form = await openEditor(page, user.email);
  await field(form, en.admin.fields.active).uncheck();
  await form.getByRole('button', { name: en.admin.edit.save }).click();
  const confirm = form.getByRole('alertdialog', { name: en.admin.edit.confirmTitle });
  await expect(confirm).toContainText(en.admin.edit.confirmBody);
  await confirm.getByRole('button', { name: en.admin.edit.confirm }).click();
  await expect(page.getByRole('status')).toHaveText(en.admin.notice.saved);
  await expect(row).toContainText(en.admin.users.inactive);

  // The server has it: after a reload the row is still an inactive editor, who can't sign in.
  await openAdmin(page);
  await expect(row).toContainText(en.roles.editor);
  await expect(row).toContainText(en.admin.users.inactive);
  const refused = await signInAsUser();
  expect(refused.status()).toBe(403);
  expect(await refused.json()).toEqual({ error: { code: 'ACCOUNT_DISABLED', params: {} } });

  // Reactivate: no confirmation needed, and they can sign in again.
  form = await openEditor(page, user.email);
  await field(form, en.admin.fields.active).check();
  await form.getByRole('button', { name: en.admin.edit.save }).click();
  await expect(page.getByRole('status')).toHaveText(en.admin.notice.saved);
  await expect(row).toContainText(en.admin.users.active);
  expect((await signInAsUser()).status()).toBe(200);
});

test('a duplicate email shows the translated error', async ({ page }) => {
  await openAdmin(page, 'ar');
  await page.getByRole('button', { name: ar.admin.create.open }).click();
  const create = page.getByRole('form', { name: ar.admin.create.heading });
  await field(create, ar.admin.fields.name).fill('هالة تجريبية');
  await field(create, ar.admin.fields.email).fill(DEMO.viewer.email);
  await field(create, ar.admin.fields.password).fill(PASSWORD);
  await create.getByRole('button', { name: ar.admin.create.submit }).click();

  await expect(create.getByRole('alert')).toHaveText(ar.errors.EMAIL_TAKEN);
  await expect(field(create, ar.admin.fields.email)).toHaveAttribute('aria-invalid', 'true');
  await expect(field(create, ar.admin.fields.email)).toHaveValue(DEMO.viewer.email);
  await expect(rowOf(page, DEMO.viewer.email)).toHaveCount(1);
});

test("the admin's own row can't be demoted or deactivated", async ({ page }) => {
  await openAdmin(page);
  const row = rowOf(page, DEMO.admin.email);
  await expect(row).toContainText(en.admin.users.you);
  const form = await openEditor(page, DEMO.admin.email);
  await expect(field(form, en.admin.fields.role)).toBeDisabled();
  await expect(field(form, en.admin.fields.role)).toHaveValue('admin');
  await expect(field(form, en.admin.fields.active)).toBeDisabled();
  await expect(field(form, en.admin.fields.active)).toBeChecked();
  await expect(field(form, en.admin.fields.language)).toBeEnabled();
  await expect(form).toContainText(en.admin.edit.selfHint);
});

test("the guest's role is shown as fixed", async ({ page }) => {
  await openAdmin(page);
  const row = rowOf(page, GUEST_EMAIL);
  await expect(row).toContainText(en.roles.guest);
  await expect(row).toContainText(en.roles.viewer);
  await expect(row).toContainText(en.admin.users.roleFixed);

  const form = await openEditor(page, GUEST_EMAIL);
  await expect(form.getByRole('combobox', { name: en.admin.fields.role })).toHaveCount(0);
  await expect(form).toContainText(en.admin.users.roleFixed);
  await expect(form).toContainText(en.admin.edit.guestHint);
  await expect(field(form, en.admin.fields.language)).toBeEnabled();
  await form.getByRole('button', { name: en.admin.edit.cancel }).click();
  await expect(form).toHaveCount(0);
});

test('a viewer visiting /admin sees the translated no-access page', async ({ page, context }) => {
  await context.clearCookies();
  await signIn(page, 'viewer');
  const adminCalls: string[] = [];
  page.on('request', (req) => {
    if (new URL(req.url()).pathname.startsWith('/api/admin/')) adminCalls.push(req.url());
  });
  await page.goto('/admin?lang=ar');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(ar.pages.forbidden.title);
  await expect(page.getByRole('main')).toContainText(ar.pages.forbidden.body);
  expect(adminCalls).toEqual([]);
});

test('a language switch keeps state and makes no GET', async ({ page }) => {
  await openAdmin(page);
  await page.getByRole('button', { name: en.admin.create.open }).click();
  const create = page.getByRole('form', { name: en.admin.create.heading });
  await field(create, en.admin.fields.name).fill('Hala Example');
  await field(create, en.admin.fields.email).fill('hala.unsaved@sanad.example');
  await field(create, en.admin.fields.role).selectOption('editor');
  const editor = await openEditor(page, GUEST_EMAIL);
  await field(editor, en.admin.fields.language).selectOption('ar');

  const gets: string[] = [];
  page.on('request', (req) => {
    if (req.method() === 'GET' && new URL(req.url()).pathname.startsWith('/api/')) {
      gets.push(req.url());
    }
  });
  // The switch saves a real user's choice (PATCH /api/me); that is not a GET.
  const saved = page.waitForResponse(
    (res) => res.request().method() === 'PATCH' && new URL(res.url()).pathname === '/api/me',
  );
  await page.getByRole('button', { name: en.language.switch }).click();
  await saved;

  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(ar.pages.admin.title);
  const createAr = page.getByRole('form', { name: ar.admin.create.heading });
  await expect(field(createAr, ar.admin.fields.name)).toHaveValue('Hala Example');
  await expect(field(createAr, ar.admin.fields.email)).toHaveValue('hala.unsaved@sanad.example');
  await expect(field(createAr, ar.admin.fields.role)).toHaveValue('editor');
  const editorAr = page.getByRole('form', { name: ar.admin.users.edit });
  await expect(field(editorAr, ar.admin.fields.language)).toHaveValue('ar');
  await expect(rowOf(page, GUEST_EMAIL)).toContainText(ar.admin.users.roleFixed);
  expect(gets).toEqual([]);

  // Back to English, which also restores the demo admin's saved language.
  const restored = page.waitForResponse(
    (res) => res.request().method() === 'PATCH' && new URL(res.url()).pathname === '/api/me',
  );
  await page.getByRole('button', { name: ar.language.switch }).click();
  await restored;
  await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
  expect(gets).toEqual([]);
});

for (const [lang, dir] of [
  ['ar', 'rtl'],
  ['en', 'ltr'],
] as const) {
  test(`the users screen is laid out ${dir} in ${lang}`, async ({ page }) => {
    const messages = await openAdmin(page, lang);
    await expect(page.locator('html')).toHaveAttribute('dir', dir);
    const header = (name: string) =>
      page.getByRole('columnheader', { name, exact: true }).boundingBox();
    const name = await header(messages.admin.fields.name);
    const email = await header(messages.admin.fields.email);
    const title = await page.getByRole('heading', { level: 1 }).boundingBox();
    const add = await page.getByRole('button', { name: messages.admin.create.open }).boundingBox();
    if (!name || !email || !title || !add) throw new Error('users screen not rendered');
    // The first column and the title sit at the inline start: right in Arabic, left in English.
    if (dir === 'rtl') {
      expect(name.x).toBeGreaterThan(email.x);
      expect(title.x).toBeGreaterThan(add.x);
    } else {
      expect(name.x).toBeLessThan(email.x);
      expect(title.x).toBeLessThan(add.x);
    }
    const info = test.info();
    const path = info.outputPath(`admin-${lang}.png`);
    await page.screenshot({ path, fullPage: true });
    await info.attach(`admin-${lang}`, { path, contentType: 'image/png' });
  });
}
