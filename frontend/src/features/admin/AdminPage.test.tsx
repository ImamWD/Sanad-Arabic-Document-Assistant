import { cleanup, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LANGUAGE_STORAGE_KEY } from '../../app/i18n';
import { type ApiCall, apiError, json, renderApp, testUser } from '../../app/test-utils';
import { createFormat } from '../../lib/format';
import ar from '../../locales/ar.json';
import en from '../../locales/en.json';
import type { Me } from '../auth/types';
import type { AdminUser } from './types';

// Synthetic, obviously fake accounts (CLAUDE.md rule 10). SELF is the signed-in admin.
const ME = testUser('admin', { preferred_language: 'en' });

function account(overrides: Partial<AdminUser> & Pick<AdminUser, 'id' | 'name' | 'email'>) {
  return {
    role: 'viewer',
    preferred_language: 'en',
    is_active: true,
    is_guest: false,
    created_at: '2026-10-01T08:00:00Z',
    updated_at: '2026-10-01T08:00:00Z',
    last_login_at: '2026-10-24T09:15:00Z',
    ...overrides,
  } satisfies AdminUser;
}

const SELF = account({ id: ME.id, name: ME.name, email: ME.email, role: 'admin' });
const GUEST_ROW = account({
  id: '00000000-0000-4000-8000-000000000010',
  name: 'Guest',
  email: 'guest@sanad.example',
  is_guest: true,
});
const VIEWER_ROW = account({
  id: '00000000-0000-4000-8000-000000000011',
  name: 'ليلى تجريبية',
  email: 'layla.example@sanad.example',
  preferred_language: 'ar',
  created_at: '2026-10-12T10:30:00Z',
  last_login_at: null,
});
const INACTIVE_ROW = account({
  id: '00000000-0000-4000-8000-000000000012',
  name: 'Sami Example',
  email: 'sami.example@sanad.example',
  role: 'editor',
  is_active: false,
});
const USERS = [SELF, GUEST_ROW, VIEWER_ROW, INACTIVE_ROW];

const NEW_USER = {
  name: 'Hala Example',
  email: 'hala.example@sanad.example',
  password: 'correct-horse-battery',
  role: 'editor',
  preferred_language: 'ar',
} as const;

type Handlers = NonNullable<Parameters<typeof renderApp>[0]>['handlers'];

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, '', '/');
});

afterEach(() => {
  cleanup();
});

const gets = (calls: ApiCall[]) => calls.filter((call) => call.method === 'GET');
const writes = (calls: ApiCall[]) => calls.filter((call) => call.method !== 'GET');
const patchOf = (user: AdminUser) => `PATCH /api/admin/users/${user.id}`;

/** "{{name}}" placeholders filled in, to compare with what the screen shows. */
function fill(template: string, values: Record<string, string>): string {
  return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) => values[name] ?? '');
}

/** PATCH handler that applies the body to `user`, like the server does. */
function patched(user: AdminUser) {
  return (body: unknown) => json(200, { ...user, ...(body as Partial<AdminUser>) });
}

async function openAdmin(handlers: Handlers = {}, me: Me = ME) {
  const messages = me.preferred_language === 'ar' ? ar : en;
  const view = await renderApp({
    path: '/admin',
    user: me,
    handlers: { 'GET /api/admin/users': () => json(200, USERS), ...handlers },
  });
  await screen.findByRole('table', { name: messages.admin.users.heading });
  return { ...view, actor: userEvent.setup(), messages };
}

function rowOf(user: Pick<AdminUser, 'email'>): HTMLElement {
  const row = screen.getAllByRole('row').find((tr) => tr.textContent.includes(user.email));
  if (!row) throw new Error(`no row for ${user.email}`);
  return row;
}

async function edit(actor: ReturnType<typeof userEvent.setup>, user: AdminUser, messages = en) {
  await actor.click(
    within(rowOf(user)).getByRole('button', {
      name: fill(messages.admin.users.editUser, { name: user.name }),
    }),
  );
  return screen.getByRole('form', { name: fill(messages.admin.edit.label, { name: user.name }) });
}

describe('users table', () => {
  it('lists every account with role, language, status and locale-formatted dates', async () => {
    const { calls } = await openAdmin();
    const format = createFormat('en', 'latn');
    expect(screen.getByRole('heading', { level: 1, name: en.pages.admin.title })).toBeDefined();
    expect(gets(calls).map((call) => call.path)).toEqual(['/api/me', '/api/admin/users']);

    const viewer = rowOf(VIEWER_ROW).textContent;
    expect(viewer).toContain(en.roles.viewer);
    expect(viewer).toContain(en.admin.languages.ar);
    expect(viewer).toContain(en.admin.users.active);
    expect(viewer).toContain(format.date(VIEWER_ROW.created_at));
    expect(viewer).toContain(en.admin.users.never);

    const self = rowOf(SELF).textContent;
    expect(self).toContain(en.admin.users.you);
    expect(self).toContain(en.roles.admin);
    expect(self).toContain(format.dateTime(SELF.last_login_at ?? ''));

    expect(rowOf(INACTIVE_ROW).textContent).toContain(en.admin.users.inactive);

    const guest = rowOf(GUEST_ROW).textContent;
    expect(guest).toContain(en.roles.guest);
    expect(guest).toContain(en.admin.users.roleFixed);
  });

  it('names and emails follow their own direction, not the locale', async () => {
    await openAdmin();
    expect(screen.getByText(VIEWER_ROW.name).getAttribute('dir')).toBe('auto');
    expect(screen.getByText(VIEWER_ROW.email).getAttribute('dir')).toBe('auto');
  });

  it('in Arabic, dates use Arabic month names and Latin digits by default', async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'ar');
    await openAdmin({}, { ...ME, preferred_language: 'ar' });
    const format = createFormat('ar', 'latn');
    const viewer = rowOf(VIEWER_ROW).textContent;
    expect(viewer).toContain(format.date(VIEWER_ROW.created_at));
    expect(viewer).toContain(ar.admin.users.never);
    expect(viewer).toContain(ar.admin.languages.ar);
    expect(format.date(VIEWER_ROW.created_at)).toMatch(/12/);
  });

  it('a failed list shows the translated error, and Try again fetches it once more', async () => {
    let fail = true;
    const view = await renderApp({
      path: '/admin',
      user: ME,
      handlers: {
        'GET /api/admin/users': () => (fail ? apiError(403, 'FORBIDDEN') : json(200, USERS)),
      },
    });
    expect((await screen.findByRole('alert')).textContent).toBe(en.errors.FORBIDDEN);
    fail = false;
    await userEvent.setup().click(screen.getByRole('button', { name: en.admin.retry }));
    expect(await screen.findByRole('table', { name: en.admin.users.heading })).toBeDefined();
    expect(gets(view.calls).filter((call) => call.path === '/api/admin/users')).toHaveLength(2);
  });

  it('a viewer gets the no-access page, and the list is never requested', async () => {
    const { calls } = await renderApp({
      path: '/admin',
      user: testUser('viewer', { preferred_language: 'en' }),
      handlers: { 'GET /api/admin/users': () => json(200, USERS) },
    });
    expect(
      await screen.findByRole('heading', { level: 1, name: en.pages.forbidden.title }),
    ).toBeDefined();
    expect(calls.some((call) => call.path.startsWith('/api/admin/'))).toBe(false);
  });
});

describe('create user', () => {
  it('sends exactly the five fields, then shows the new row without refetching', async () => {
    const created = account({
      id: '00000000-0000-4000-8000-000000000020',
      name: NEW_USER.name,
      email: NEW_USER.email,
      role: NEW_USER.role,
      preferred_language: NEW_USER.preferred_language,
    });
    const { actor, calls } = await openAdmin({
      'POST /api/admin/users': () => json(201, created),
    });
    await actor.click(screen.getByRole('button', { name: en.admin.create.open }));
    const form = screen.getByRole('form', { name: en.admin.create.heading });
    expect(document.activeElement).toBe(within(form).getByLabelText(en.admin.fields.name));

    await actor.type(within(form).getByLabelText(en.admin.fields.name), `  ${NEW_USER.name} `);
    await actor.type(within(form).getByLabelText(en.admin.fields.email), NEW_USER.email);
    await actor.type(within(form).getByLabelText(en.admin.fields.password), NEW_USER.password);
    await actor.selectOptions(within(form).getByLabelText(en.admin.fields.role), 'editor');
    await actor.selectOptions(within(form).getByLabelText(en.admin.fields.language), 'ar');
    await actor.click(within(form).getByRole('button', { name: en.admin.create.submit }));

    await screen.findByText(en.admin.notice.created);
    expect(screen.getByRole('status').textContent).toBe(en.admin.notice.created);
    expect(writes(calls)).toEqual([
      { method: 'POST', path: '/api/admin/users', body: { ...NEW_USER } },
    ]);
    expect(rowOf(created).textContent).toContain(en.roles.editor);
    expect(screen.queryByRole('form', { name: en.admin.create.heading })).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: en.admin.create.open }));
    expect(gets(calls).filter((call) => call.path === '/api/admin/users')).toHaveLength(1);
  });

  it('defaults to the least privilege and to the language on screen', async () => {
    const { actor } = await openAdmin();
    await actor.click(screen.getByRole('button', { name: en.admin.create.open }));
    const form = screen.getByRole('form', { name: en.admin.create.heading });
    expect(within(form).getByLabelText<HTMLSelectElement>(en.admin.fields.role).value).toBe(
      'viewer',
    );
    expect(within(form).getByLabelText<HTMLSelectElement>(en.admin.fields.language).value).toBe(
      'en',
    );
  });

  it('catches missing fields before any request', async () => {
    const { actor, calls } = await openAdmin();
    await actor.click(screen.getByRole('button', { name: en.admin.create.open }));
    const form = screen.getByRole('form', { name: en.admin.create.heading });
    await actor.type(within(form).getByLabelText(en.admin.fields.name), NEW_USER.name);
    await actor.click(within(form).getByRole('button', { name: en.admin.create.submit }));

    expect(within(form).getByRole('alert').textContent).toBe(en.admin.create.missingFields);
    const email = within(form).getByLabelText(en.admin.fields.email);
    expect(email.getAttribute('aria-invalid')).toBe('true');
    expect(within(form).getByLabelText(en.admin.fields.name).getAttribute('aria-invalid')).toBe(
      null,
    );
    expect(writes(calls)).toEqual([]);
  });

  it('a duplicate email shows the translated error and keeps what was typed', async () => {
    const { actor } = await openAdmin({
      'POST /api/admin/users': () => apiError(409, 'EMAIL_TAKEN'),
    });
    await actor.click(screen.getByRole('button', { name: en.admin.create.open }));
    const form = screen.getByRole('form', { name: en.admin.create.heading });
    await actor.type(within(form).getByLabelText(en.admin.fields.name), NEW_USER.name);
    await actor.type(within(form).getByLabelText(en.admin.fields.email), VIEWER_ROW.email);
    await actor.type(within(form).getByLabelText(en.admin.fields.password), NEW_USER.password);
    await actor.click(within(form).getByRole('button', { name: en.admin.create.submit }));

    expect((await within(form).findByRole('alert')).textContent).toBe(en.errors.EMAIL_TAKEN);
    const email = within(form).getByLabelText<HTMLInputElement>(en.admin.fields.email);
    expect(email.getAttribute('aria-invalid')).toBe('true');
    expect(email.value).toBe(VIEWER_ROW.email);
    expect(within(form).getByLabelText<HTMLInputElement>(en.admin.fields.name).value).toBe(
      NEW_USER.name,
    );
  });

  it('a short password shows the minimum the server asks for', async () => {
    const { actor } = await openAdmin({
      'POST /api/admin/users': () => apiError(422, 'PASSWORD_TOO_SHORT', { min_length: 12 }),
    });
    await actor.click(screen.getByRole('button', { name: en.admin.create.open }));
    const form = screen.getByRole('form', { name: en.admin.create.heading });
    await actor.type(within(form).getByLabelText(en.admin.fields.name), NEW_USER.name);
    await actor.type(within(form).getByLabelText(en.admin.fields.email), NEW_USER.email);
    await actor.type(within(form).getByLabelText(en.admin.fields.password), 'short');
    await actor.click(within(form).getByRole('button', { name: en.admin.create.submit }));

    expect((await within(form).findByRole('alert')).textContent).toBe(
      fill(en.errors.PASSWORD_TOO_SHORT, { min_length: '12' }),
    );
    expect(within(form).getByLabelText(en.admin.fields.password).getAttribute('aria-invalid')).toBe(
      'true',
    );
  });

  it('a VALIDATION_ERROR marks the fields the server names', async () => {
    const { actor } = await openAdmin({
      'POST /api/admin/users': () => apiError(422, 'VALIDATION_ERROR', { fields: ['body.email'] }),
    });
    await actor.click(screen.getByRole('button', { name: en.admin.create.open }));
    const form = screen.getByRole('form', { name: en.admin.create.heading });
    await actor.type(within(form).getByLabelText(en.admin.fields.name), NEW_USER.name);
    await actor.type(within(form).getByLabelText(en.admin.fields.email), 'hala@localhost');
    await actor.type(within(form).getByLabelText(en.admin.fields.password), NEW_USER.password);
    await actor.click(within(form).getByRole('button', { name: en.admin.create.submit }));

    expect((await within(form).findByRole('alert')).textContent).toBe(en.errors.VALIDATION_ERROR);
    expect(within(form).getByLabelText(en.admin.fields.email).getAttribute('aria-invalid')).toBe(
      'true',
    );
  });
});

describe('edit user', () => {
  it('changes the role: the PATCH carries only what changed', async () => {
    const { actor, calls } = await openAdmin({ [patchOf(VIEWER_ROW)]: patched(VIEWER_ROW) });
    const form = await edit(actor, VIEWER_ROW);
    await actor.selectOptions(within(form).getByLabelText(en.admin.fields.role), 'editor');
    await actor.click(within(form).getByRole('button', { name: en.admin.edit.save }));

    await screen.findByText(en.admin.notice.saved);
    expect(screen.getByRole('status').textContent).toBe(en.admin.notice.saved);
    expect(writes(calls)).toEqual([
      { method: 'PATCH', path: `/api/admin/users/${VIEWER_ROW.id}`, body: { role: 'editor' } },
    ]);
    expect(rowOf(VIEWER_ROW).textContent).toContain(en.roles.editor);
    expect(gets(calls).filter((call) => call.path === '/api/admin/users')).toHaveLength(1);
    // Focus goes back to the row's Edit button.
    expect(document.activeElement).toBe(
      within(rowOf(VIEWER_ROW)).getByRole('button', {
        name: fill(en.admin.users.editUser, { name: VIEWER_ROW.name }),
      }),
    );
  });

  it('Save with nothing changed sends nothing', async () => {
    const { actor, calls } = await openAdmin();
    const form = await edit(actor, VIEWER_ROW);
    await actor.click(within(form).getByRole('button', { name: en.admin.edit.save }));
    expect(screen.queryByRole('form')).toBeNull();
    expect(writes(calls)).toEqual([]);
  });

  it('deactivating asks first; Go back sends nothing, Deactivate sends is_active only', async () => {
    const { actor, calls } = await openAdmin({ [patchOf(VIEWER_ROW)]: patched(VIEWER_ROW) });
    const form = await edit(actor, VIEWER_ROW);
    await actor.click(within(form).getByLabelText(en.admin.fields.active));
    await actor.click(within(form).getByRole('button', { name: en.admin.edit.save }));

    const confirm = within(form).getByRole('alertdialog', { name: en.admin.edit.confirmTitle });
    expect(confirm.textContent).toContain(en.admin.edit.confirmBody);
    expect(document.activeElement).toBe(
      within(confirm).getByRole('button', { name: en.admin.edit.back }),
    );
    expect(writes(calls)).toEqual([]);

    await actor.click(within(confirm).getByRole('button', { name: en.admin.edit.back }));
    expect(within(form).queryByRole('alertdialog')).toBeNull();
    expect(writes(calls)).toEqual([]);

    await actor.click(within(form).getByRole('button', { name: en.admin.edit.save }));
    await actor.click(
      within(within(form).getByRole('alertdialog')).getByRole('button', {
        name: en.admin.edit.confirm,
      }),
    );
    await screen.findByText(en.admin.notice.saved);
    expect(screen.getByRole('status').textContent).toBe(en.admin.notice.saved);
    expect(writes(calls)).toEqual([
      { method: 'PATCH', path: `/api/admin/users/${VIEWER_ROW.id}`, body: { is_active: false } },
    ]);
    expect(rowOf(VIEWER_ROW).textContent).toContain(en.admin.users.inactive);
  });

  it('reactivating needs no confirmation', async () => {
    const { actor, calls } = await openAdmin({ [patchOf(INACTIVE_ROW)]: patched(INACTIVE_ROW) });
    const form = await edit(actor, INACTIVE_ROW);
    await actor.click(within(form).getByLabelText(en.admin.fields.active));
    await actor.click(within(form).getByRole('button', { name: en.admin.edit.save }));

    await screen.findByText(en.admin.notice.saved);
    expect(screen.getByRole('status').textContent).toBe(en.admin.notice.saved);
    expect(writes(calls)).toEqual([
      { method: 'PATCH', path: `/api/admin/users/${INACTIVE_ROW.id}`, body: { is_active: true } },
    ]);
    expect(rowOf(INACTIVE_ROW).textContent).toContain(en.admin.users.active);
  });

  it("the admin's own row: role and active are disabled, language is not", async () => {
    const { actor } = await openAdmin();
    const form = await edit(actor, SELF);
    const role = within(form).getByLabelText<HTMLSelectElement>(en.admin.fields.role);
    const active = within(form).getByLabelText<HTMLInputElement>(en.admin.fields.active);
    expect(role.disabled).toBe(true);
    expect(active.disabled).toBe(true);
    expect(within(form).getByLabelText<HTMLSelectElement>(en.admin.fields.language).disabled).toBe(
      false,
    );
    expect(within(form).getByText(en.admin.edit.selfHint)).toBeDefined();
    expect(role.getAttribute('aria-describedby')).toBe(
      within(form).getByText(en.admin.edit.selfHint).id,
    );
  });

  it("the admin's own language can change; role and active are never sent", async () => {
    const { actor, calls } = await openAdmin({ [patchOf(SELF)]: patched(SELF) });
    const form = await edit(actor, SELF);
    await actor.selectOptions(within(form).getByLabelText(en.admin.fields.language), 'ar');
    await actor.click(within(form).getByRole('button', { name: en.admin.edit.save }));
    await screen.findByText(en.admin.notice.saved);
    expect(writes(calls)).toEqual([
      { method: 'PATCH', path: `/api/admin/users/${SELF.id}`, body: { preferred_language: 'ar' } },
    ]);
  });

  it("the guest's role is shown as fixed text, not a control", async () => {
    const { actor } = await openAdmin();
    const form = await edit(actor, GUEST_ROW);
    expect(within(form).queryByRole('combobox', { name: en.admin.fields.role })).toBeNull();
    expect(within(form).getByText(en.admin.users.roleFixed)).toBeDefined();
    expect(within(form).getByText(en.admin.edit.guestHint)).toBeDefined();
    expect(within(form).getByRole('combobox', { name: en.admin.fields.language })).toBeDefined();
  });

  it('a refused change shows the translated code and keeps the form open', async () => {
    const { actor } = await openAdmin({
      [patchOf(VIEWER_ROW)]: () => apiError(409, 'CANNOT_CHANGE_OWN_ACCESS'),
    });
    const form = await edit(actor, VIEWER_ROW);
    await actor.selectOptions(within(form).getByLabelText(en.admin.fields.role), 'admin');
    await actor.click(within(form).getByRole('button', { name: en.admin.edit.save }));
    expect((await within(form).findByRole('alert')).textContent).toBe(
      en.errors.CANNOT_CHANGE_OWN_ACCESS,
    );
    expect(rowOf(VIEWER_ROW).textContent).toContain(en.roles.viewer);
  });

  it('Cancel closes the form and returns focus to its Edit button', async () => {
    const { actor, calls } = await openAdmin();
    const form = await edit(actor, VIEWER_ROW);
    await actor.selectOptions(within(form).getByLabelText(en.admin.fields.role), 'admin');
    await actor.click(within(form).getByRole('button', { name: en.admin.edit.cancel }));
    expect(screen.queryByRole('form')).toBeNull();
    expect(writes(calls)).toEqual([]);
    expect(document.activeElement).toBe(
      within(rowOf(VIEWER_ROW)).getByRole('button', {
        name: fill(en.admin.users.editUser, { name: VIEWER_ROW.name }),
      }),
    );
  });
});

describe('language switch', () => {
  it('keeps a half-filled create form and the notice, and makes no GET', async () => {
    const { actor, calls } = await openAdmin({ [patchOf(INACTIVE_ROW)]: patched(INACTIVE_ROW) });
    await actor.click(screen.getByRole('button', { name: en.admin.create.open }));
    const create = screen.getByRole('form', { name: en.admin.create.heading });
    await actor.type(within(create).getByLabelText(en.admin.fields.name), NEW_USER.name);
    await actor.type(within(create).getByLabelText(en.admin.fields.email), NEW_USER.email);
    await actor.selectOptions(within(create).getByLabelText(en.admin.fields.role), 'editor');
    // A saved change, so there is a notice to re-translate.
    const form = await edit(actor, INACTIVE_ROW);
    await actor.click(within(form).getByLabelText(en.admin.fields.active));
    await actor.click(within(form).getByRole('button', { name: en.admin.edit.save }));
    await screen.findByText(en.admin.notice.saved);
    const before = gets(calls).length;

    await actor.click(screen.getByRole('button', { name: en.language.switch }));

    expect(document.documentElement.dir).toBe('rtl');
    expect(screen.getByRole('heading', { level: 1, name: ar.pages.admin.title })).toBeDefined();
    const createAr = screen.getByRole('form', { name: ar.admin.create.heading });
    expect(within(createAr).getByLabelText<HTMLInputElement>(ar.admin.fields.name).value).toBe(
      NEW_USER.name,
    );
    expect(within(createAr).getByLabelText<HTMLInputElement>(ar.admin.fields.email).value).toBe(
      NEW_USER.email,
    );
    expect(within(createAr).getByLabelText<HTMLSelectElement>(ar.admin.fields.role).value).toBe(
      'editor',
    );
    expect(screen.getByRole('status').textContent).toBe(ar.admin.notice.saved);
    expect(rowOf(INACTIVE_ROW).textContent).toContain(ar.admin.users.active);
    expect(rowOf(VIEWER_ROW).textContent).toContain(ar.admin.users.never);
    expect(gets(calls).length).toBe(before);
  });

  it("keeps an open editor's unsaved choice and makes no GET", async () => {
    const { actor, calls } = await openAdmin();
    const form = await edit(actor, VIEWER_ROW);
    await actor.selectOptions(within(form).getByLabelText(en.admin.fields.role), 'editor');
    await actor.click(within(form).getByLabelText(en.admin.fields.active));
    const before = gets(calls).length;

    await actor.click(screen.getByRole('button', { name: en.language.switch }));

    const formAr = screen.getByRole('form', {
      name: fill(ar.admin.edit.label, { name: VIEWER_ROW.name }),
    });
    expect(within(formAr).getByLabelText<HTMLSelectElement>(ar.admin.fields.role).value).toBe(
      'editor',
    );
    expect(within(formAr).getByLabelText<HTMLInputElement>(ar.admin.fields.active).checked).toBe(
      false,
    );
    expect(gets(calls).length).toBe(before);
    expect(writes(calls).filter((call) => call.path.startsWith('/api/admin/'))).toEqual([]);
  });
});
