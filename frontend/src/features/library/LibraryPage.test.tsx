import { act, cleanup, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { apiError, json, renderApp, testUser } from '../../app/test-utils';
import ar from '../../locales/ar.json';
import en from '../../locales/en.json';
import {
  ANNUAL_REPORT,
  listOf,
  PROGRAMMES,
  RESTRICTED_AGREEMENT,
  SCANNED_MINUTES,
  UNCATEGORISED_SURVEY,
} from './test-fixtures';
import type { DocumentItem } from './types';

const EN_EDITOR = testUser('editor', { preferred_language: 'en' });
const EN_VIEWER = testUser('viewer', { preferred_language: 'en' });
const AR_EDITOR = testUser('editor', { preferred_language: 'ar' });
const ALL = [ANNUAL_REPORT, RESTRICTED_AGREEMENT, UNCATEGORISED_SURVEY, SCANNED_MINUTES];

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, '', '/');
  // Radix measures its popper with ResizeObserver, which jsdom lacks.
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();
    },
  );
  // jsdom has <dialog> but not its modal methods.
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.open = false;
  };
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function libraryHandlers(items: DocumentItem[] = ALL) {
  return {
    'GET /api/documents': () => json(200, listOf(items)),
    'GET /api/programmes': () => json(200, PROGRAMMES),
  };
}

/** The query strings of every GET /api/documents, in order. */
function listRequests(fetchSpy: { mock: { calls: unknown[][] } }): URLSearchParams[] {
  return fetchSpy.mock.calls
    .map(([input]) => new URL(String(input), 'http://sanad.test'))
    .filter((url) => url.pathname === '/api/documents')
    .map((url) => url.searchParams);
}

/** A document's row. Titles can't be matched as one text: <Bidi> isolates their Latin runs. */
function rowOf(document: DocumentItem): HTMLElement {
  const row = window.document.querySelector<HTMLElement>(`tr[data-document-id="${document.id}"]`);
  if (!row) throw new Error(`no row for ${document.id}`);
  return row;
}

/** Wait until the table has rendered. */
const tableShown = () => screen.findByText(ANNUAL_REPORT.title);

describe('Library table', () => {
  it('lists every column, with the programme name in the UI language', async () => {
    await renderApp({ path: '/library', user: EN_EDITOR, handlers: libraryHandlers() });
    await tableShown();
    const headers = screen.getAllByRole('columnheader').map((th) => th.textContent);
    expect(headers).toEqual([
      en.library.table.title,
      en.library.table.fileType,
      en.library.table.category,
      en.library.table.year,
      en.library.table.programme,
      en.library.table.uploadedBy,
      en.library.table.uploadedAt,
      en.library.table.pages,
      en.library.table.status,
      en.library.table.actions,
    ]);
    const row = within(rowOf(RESTRICTED_AGREEMENT));
    expect(row.getByText(PROGRAMMES[1]?.name_en ?? '')).toBeDefined();
    expect(row.getByText(en.documents.category.donor_agreement)).toBeDefined();
    expect(row.getByText('2022')).toBeDefined();
    expect(row.getByText('Sami Example')).toBeDefined();
    expect(
      screen.getByText(
        en.library.summary
          .replace('{{from}}', '1')
          .replace('{{to}}', '4')
          .replace('{{total}}', '4'),
      ),
    ).toBeDefined();
  });

  it('shows the restricted badge and the actions to an editor', async () => {
    await renderApp({ path: '/library', user: EN_EDITOR, handlers: libraryHandlers() });
    await tableShown();
    const row = within(rowOf(RESTRICTED_AGREEMENT));
    expect(row.getByText(en.documents.restricted)).toBeDefined();
    expect(within(rowOf(ANNUAL_REPORT)).queryByText(en.documents.restricted)).toBeNull();
    expect(screen.getAllByRole('button', { name: /^Actions for/ })).toHaveLength(4);
    expect(screen.getByLabelText(en.library.filters.access)).toBeDefined();
  });

  it('never shows a viewer the restricted badge, the access filter or the actions', async () => {
    // The server never sends a viewer a restricted document; the screen doesn't rely on it.
    await renderApp({ path: '/library', user: EN_VIEWER, handlers: libraryHandlers() });
    await tableShown();
    expect(screen.queryByText(en.documents.restricted)).toBeNull();
    expect(screen.queryByLabelText(en.library.filters.access)).toBeNull();
    expect(screen.queryByRole('button', { name: /^Actions for/ })).toBeNull();
    expect(screen.queryByRole('columnheader', { name: en.library.table.actions })).toBeNull();
  });

  it('flags a document with no category for review', async () => {
    await renderApp({ path: '/library', user: AR_EDITOR, handlers: libraryHandlers() });
    await tableShown();
    expect(within(rowOf(UNCATEGORISED_SURVEY)).getByText(ar.documents.category.none)).toBeDefined();
  });

  it.each([
    ['en', EN_EDITOR, en],
    ['ar', AR_EDITOR, ar],
  ] as const)('gives a failed row its translated reason (%s)', async (_lang, user, messages) => {
    await renderApp({ path: '/library', user, handlers: libraryHandlers() });
    await tableShown();
    const row = within(rowOf(SCANNED_MINUTES));
    expect(row.getByText(messages.documents.status.failed)).toBeDefined();
    expect(row.getByText(messages.errors.NO_TEXT_LAYER)).toBeDefined();
  });

  it('gives an unknown failure code the generic message, never the code', async () => {
    const odd = { ...SCANNED_MINUTES, error_code: 'SOMETHING_NEW' };
    await renderApp({ path: '/library', user: EN_EDITOR, handlers: libraryHandlers([odd]) });
    await screen.findByText(en.errors.UNKNOWN_ERROR);
    expect(screen.getByText(en.errors.UNKNOWN_ERROR)).toBeDefined();
    expect(screen.queryByText(/SOMETHING_NEW/)).toBeNull();
  });

  it('opens the viewer when a row is clicked', async () => {
    const actor = userEvent.setup();
    const { router } = await renderApp({
      path: '/library',
      user: EN_EDITOR,
      handlers: {
        ...libraryHandlers(),
        [`GET /api/documents/${ANNUAL_REPORT.id}`]: () => json(200, ANNUAL_REPORT),
      },
    });
    await tableShown();
    await actor.click(within(rowOf(ANNUAL_REPORT)).getByText('16'));
    expect(router.state.location.pathname).toBe(`/documents/${ANNUAL_REPORT.id}`);
  });

  it('says so when nothing matches the filters', async () => {
    await renderApp({
      path: '/library?category=budget',
      user: EN_EDITOR,
      handlers: libraryHandlers([]),
    });
    expect(await screen.findByText(en.library.emptyFiltered)).toBeDefined();
  });

  it('shows a translated error when the list fails', async () => {
    await renderApp({
      path: '/library',
      user: EN_EDITOR,
      // A 4xx: no retry, so the message shows at once.
      handlers: { 'GET /api/documents': () => apiError(422, 'VALIDATION_ERROR') },
    });
    expect((await screen.findByRole('alert')).textContent).toBe(en.errors.VALIDATION_ERROR);
  });
});

describe('Library filters', () => {
  it('sends each filter to the server and keeps it in the URL', async () => {
    const actor = userEvent.setup();
    const { fetchSpy, router } = await renderApp({
      path: '/library',
      user: EN_EDITOR,
      handlers: libraryHandlers(),
    });
    await tableShown();

    await actor.selectOptions(screen.getByLabelText(en.library.filters.category), 'none');
    await actor.selectOptions(screen.getByLabelText(en.library.filters.fileType), 'pdf');
    await actor.selectOptions(screen.getByLabelText(en.library.filters.status), 'failed');
    await actor.type(screen.getByLabelText(en.library.filters.yearFrom), '2015');
    await actor.selectOptions(
      screen.getByLabelText(en.library.filters.programme),
      PROGRAMMES[0]?.id ?? '',
    );

    const last = listRequests(fetchSpy).at(-1);
    expect(last?.get('uncategorised')).toBe('true');
    expect(last?.getAll('file_type')).toEqual(['pdf']);
    expect(last?.getAll('status')).toEqual(['failed']);
    expect(last?.get('year_from')).toBe('2015');
    expect(last?.getAll('programme_id')).toEqual([PROGRAMMES[0]?.id]);
    expect(router.state.location.search).toBe(
      `?type=pdf&category=none&from=2015&programme=${PROGRAMMES[0]?.id ?? ''}&status=failed`,
    );
    // An unfinished year ("201") never reaches the server.
    expect(listRequests(fetchSpy).some((params) => params.get('year_from') === '201')).toBe(false);

    await actor.click(screen.getByRole('button', { name: en.library.filters.clear }));
    expect(router.state.location.search).toBe('');
  });

  it('searches titles after a short pause', async () => {
    const actor = userEvent.setup();
    const { fetchSpy } = await renderApp({
      path: '/library',
      user: EN_EDITOR,
      handlers: libraryHandlers(),
    });
    await tableShown();
    await actor.type(screen.getByLabelText(en.library.search.label), 'التعليم');
    await vi.waitFor(() => {
      expect(listRequests(fetchSpy).at(-1)?.get('q')).toBe('التعليم');
    });
    // One request for the finished word, not one per letter.
    expect(listRequests(fetchSpy).filter((params) => params.has('q'))).toHaveLength(1);
  });

  it('keeps the filters and makes no GET when the language switches', async () => {
    const actor = userEvent.setup();
    const { calls, router } = await renderApp({
      path: '/library?category=annual_report&q=Annual',
      user: EN_EDITOR,
      handlers: { ...libraryHandlers(), 'PATCH /api/me': () => json(200, EN_EDITOR) },
    });
    await tableShown();
    const gets = () => calls.filter((call) => call.method === 'GET').length;
    const before = gets();

    await actor.click(screen.getByRole('button', { name: en.language.switch }));

    expect(await screen.findByRole('heading', { name: ar.pages.library.title })).toBeDefined();
    expect(screen.getByLabelText<HTMLSelectElement>(ar.library.filters.category).value).toBe(
      'annual_report',
    );
    expect(screen.getByLabelText<HTMLInputElement>(ar.library.search.label).value).toBe('Annual');
    expect(
      within(rowOf(RESTRICTED_AGREEMENT)).getByText(PROGRAMMES[1]?.name_ar ?? ''),
    ).toBeDefined();
    expect(router.state.location.search).toBe('?category=annual_report&q=Annual');
    expect(gets()).toBe(before);
  });
});

describe('editor actions', () => {
  async function openActions(actor: ReturnType<typeof userEvent.setup>, title: string) {
    await actor.click(screen.getByRole('button', { name: `Actions for ${title}` }));
    return screen.findByRole('menu');
  }

  it('archives a document and refreshes the list', async () => {
    const actor = userEvent.setup();
    const { calls, fetchSpy } = await renderApp({
      path: '/library',
      user: EN_EDITOR,
      handlers: {
        ...libraryHandlers(),
        [`POST /api/documents/${ANNUAL_REPORT.id}/archive`]: () =>
          json(200, { ...ANNUAL_REPORT, is_archived: true }),
      },
    });
    await tableShown();
    const listsBefore = listRequests(fetchSpy).length;

    const menu = await openActions(actor, ANNUAL_REPORT.title);
    await actor.click(within(menu).getByRole('menuitem', { name: en.library.actions.archive }));

    const post = calls.find((call) => call.method === 'POST');
    expect(post?.path).toBe(`/api/documents/${ANNUAL_REPORT.id}/archive`);
    const init = fetchSpy.mock.calls.find(([, i]) => i?.method === 'POST')?.[1];
    expect(new Headers(init?.headers).get('X-Sanad')).toBe('1');
    await vi.waitFor(() => {
      expect(listRequests(fetchSpy).length).toBeGreaterThan(listsBefore);
    });
  });

  it('offers retry only on a failed document, and sends it', async () => {
    const actor = userEvent.setup();
    const { calls } = await renderApp({
      path: '/library',
      user: EN_EDITOR,
      handlers: {
        ...libraryHandlers(),
        [`POST /api/documents/${SCANNED_MINUTES.id}/retry`]: () =>
          json(200, { ...SCANNED_MINUTES, status: 'queued', error_code: null }),
      },
    });
    await tableShown();

    let menu = await openActions(actor, ANNUAL_REPORT.title);
    expect(within(menu).queryByRole('menuitem', { name: en.library.actions.retry })).toBeNull();
    await actor.keyboard('{Escape}');

    menu = await openActions(actor, SCANNED_MINUTES.title);
    await actor.click(within(menu).getByRole('menuitem', { name: en.library.actions.retry }));
    expect(calls.some((call) => call.path === `/api/documents/${SCANNED_MINUTES.id}/retry`)).toBe(
      true,
    );
  });

  it('toggles the restricted flag with PATCH', async () => {
    const actor = userEvent.setup();
    const { calls } = await renderApp({
      path: '/library',
      user: EN_EDITOR,
      handlers: {
        ...libraryHandlers(),
        [`PATCH /api/documents/${RESTRICTED_AGREEMENT.id}`]: () =>
          json(200, { ...RESTRICTED_AGREEMENT, restricted: false }),
      },
    });
    await tableShown();
    const menu = await openActions(actor, RESTRICTED_AGREEMENT.title);
    await actor.click(within(menu).getByRole('menuitem', { name: en.library.actions.unrestrict }));
    expect(calls.find((call) => call.method === 'PATCH')?.body).toEqual({ restricted: false });
  });

  it('shows the translated reason when an action is refused', async () => {
    const actor = userEvent.setup();
    const archived = { ...ANNUAL_REPORT, is_archived: true };
    await renderApp({
      path: '/library?archived=1',
      user: EN_EDITOR,
      handlers: {
        ...libraryHandlers([archived]),
        [`POST /api/documents/${archived.id}/unarchive`]: () =>
          apiError(409, 'DUPLICATE_DOCUMENT', { document_id: 'other' }),
      },
    });
    expect(await screen.findByText(en.documents.archived)).toBeDefined();
    const menu = await openActions(actor, archived.title);
    await actor.click(within(menu).getByRole('menuitem', { name: en.library.actions.unarchive }));
    expect((await screen.findByRole('alert')).textContent).toBe(en.errors.DUPLICATE_DOCUMENT);
  });

  it('edits the metadata and sends only what changed', async () => {
    const actor = userEvent.setup();
    const { calls } = await renderApp({
      path: '/library',
      user: EN_EDITOR,
      handlers: {
        ...libraryHandlers(),
        [`PATCH /api/documents/${UNCATEGORISED_SURVEY.id}`]: (body) =>
          json(200, { ...UNCATEGORISED_SURVEY, ...(body as object) }),
      },
    });
    await tableShown();
    const menu = await openActions(actor, UNCATEGORISED_SURVEY.title);
    await actor.click(within(menu).getByRole('menuitem', { name: en.library.actions.edit }));

    const dialog = within(await screen.findByRole('dialog', { name: en.library.edit.heading }));
    await actor.selectOptions(dialog.getByLabelText(en.library.edit.category), 'field_survey');
    const year = dialog.getByLabelText(en.library.edit.year);
    await actor.clear(year);
    await actor.type(year, '20');
    await actor.click(dialog.getByRole('button', { name: en.library.edit.save }));
    expect(dialog.getByRole('alert').textContent).toBe(
      en.library.edit.yearInvalid.replace('{{min}}', '1900').replace('{{max}}', '2100'),
    );
    expect(calls.some((call) => call.method === 'PATCH')).toBe(false);

    await actor.type(year, '16');
    await act(() => actor.click(dialog.getByRole('button', { name: en.library.edit.save })));
    expect(calls.find((call) => call.method === 'PATCH')?.body).toEqual({
      category: 'field_survey',
      year: 2016,
    });
    await vi.waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull();
    });
  });
});
