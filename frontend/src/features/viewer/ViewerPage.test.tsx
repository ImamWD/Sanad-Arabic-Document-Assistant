import { act, cleanup, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { apiError, json, renderApp, testUser } from '../../app/test-utils';
import ar from '../../locales/ar.json';
import en from '../../locales/en.json';
import {
  ANNUAL_REPORT,
  BUDGET_DOCX,
  makeDocument,
  PROGRAMMES,
  RESTRICTED_AGREEMENT,
  SCANNED_MINUTES,
} from '../library/test-fixtures';
import type { DocumentItem } from '../library/types';

// pdf.js needs a real browser (workers, canvas); the e2e specs run it for real. Here a fake
// document stands in, so the tests cover the viewer's own behaviour.
const pdfMock = vi.hoisted(() => ({ pages: 12, fail: false, opened: [] as Uint8Array[] }));
vi.mock('./pdf', () => ({
  openPdf: (data: Uint8Array) => {
    pdfMock.opened.push(data);
    const page = (n: number) => ({
      pageNumber: n,
      getViewport: ({ scale }: { scale: number }) => ({ width: 595 * scale, height: 842 * scale }),
      render: () => ({ promise: Promise.resolve(), cancel: () => undefined }),
    });
    return {
      promise: pdfMock.fail
        ? Promise.reject(new Error('Invalid PDF structure'))
        : Promise.resolve({
            numPages: pdfMock.pages,
            getPage: (n: number) => Promise.resolve(page(n)),
          }),
      destroy: () => Promise.resolve(),
    };
  },
}));

const EN_VIEWER = testUser('viewer', { preferred_language: 'en' });
const EN_EDITOR = testUser('editor', { preferred_language: 'en' });
const AR_VIEWER = testUser('viewer', { preferred_language: 'ar' });
const PDF_BYTES = new TextEncoder().encode('%PDF-1.7 synthetic');

const scrolled: Element[] = [];

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, '', '/');
  pdfMock.pages = 12;
  pdfMock.fail = false;
  pdfMock.opened = [];
  scrolled.length = 0;
  Element.prototype.scrollIntoView = function scrollIntoView(this: Element) {
    scrolled.push(this);
  };
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      observe = vi.fn();
      disconnect = vi.fn();
    },
  );
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe = vi.fn();
      disconnect = vi.fn();
    },
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function handlersFor(doc: DocumentItem) {
  return {
    'GET /api/programmes': () => json(200, PROGRAMMES),
    [`GET /api/documents/${doc.id}`]: () => json(200, doc),
    [`GET /api/documents/${doc.id}/file`]: () =>
      new Response(PDF_BYTES, { status: 200, headers: { 'Content-Type': 'application/pdf' } }),
  };
}

const pageGroup = (label: string) => screen.getByRole('group', { name: label });
const lastScrolled = () => (scrolled.at(-1) as HTMLElement | undefined)?.dataset.pageNumber;

describe('viewer', () => {
  it('opens at ?page=N, scrolls to that page and marks it as cited', async () => {
    await renderApp({
      path: `/documents/${ANNUAL_REPORT.id}?page=7`,
      user: EN_VIEWER,
      handlers: handlersFor(ANNUAL_REPORT),
    });
    expect(
      await screen.findByRole('heading', { level: 1, name: ANNUAL_REPORT.title }),
    ).toBeDefined();
    await screen.findByRole('group', { name: 'Page 12' });

    const cited = pageGroup('Page 7');
    expect(cited.getAttribute('aria-current')).toBe('true');
    expect(cited.dataset.cited).toBe('true');
    expect(within(cited).getAllByText(en.viewer.citedPage).length).toBeGreaterThan(0);
    expect(document.querySelectorAll('[data-cited]')).toHaveLength(1);
    await vi.waitFor(() => {
      expect(lastScrolled()).toBe('7');
    });
    expect(screen.getByLabelText<HTMLInputElement>(en.viewer.toolbar.pageInput).value).toBe('7');
    expect(screen.getByText('of 12')).toBeDefined();
    expect(pdfMock.opened).toHaveLength(1);
  });

  it('moves between pages from the toolbar', async () => {
    const actor = userEvent.setup();
    await renderApp({
      path: `/documents/${ANNUAL_REPORT.id}?page=3`,
      user: EN_VIEWER,
      handlers: handlersFor(ANNUAL_REPORT),
    });
    await screen.findByRole('group', { name: 'Page 3' });
    await vi.waitFor(() => {
      expect(lastScrolled()).toBe('3');
    });

    await actor.click(screen.getByRole('button', { name: en.viewer.toolbar.next }));
    expect(lastScrolled()).toBe('4');
    await actor.click(screen.getByRole('button', { name: en.viewer.toolbar.previous }));
    await actor.click(screen.getByRole('button', { name: en.viewer.toolbar.previous }));
    expect(lastScrolled()).toBe('2');

    const input = screen.getByLabelText(en.viewer.toolbar.pageInput);
    await actor.clear(input);
    await actor.type(input, '99{Enter}');
    expect(lastScrolled()).toBe('12');
    expect(
      screen.getByRole<HTMLButtonElement>('button', { name: en.viewer.toolbar.next }).disabled,
    ).toBe(true);

    await actor.click(
      screen.getByRole('button', { name: en.viewer.toolbar.goToCited.replace('{{page}}', '3') }),
    );
    expect(lastScrolled()).toBe('3');
  });

  it('opens at the top with no page marked when ?page= is missing or out of range', async () => {
    await renderApp({
      path: `/documents/${ANNUAL_REPORT.id}?page=40`,
      user: EN_VIEWER,
      handlers: handlersFor(ANNUAL_REPORT),
    });
    await screen.findByRole('group', { name: 'Page 12' });
    expect(document.querySelector('[data-cited]')).toBeNull();
    expect(screen.queryByRole('button', { name: /cited page/ })).toBeNull();
    expect(screen.getByLabelText<HTMLInputElement>(en.viewer.toolbar.pageInput).value).toBe('1');
  });

  it('shows the title and the metadata', async () => {
    await renderApp({
      path: `/documents/${RESTRICTED_AGREEMENT.id}?page=2`,
      user: EN_EDITOR,
      handlers: handlersFor(RESTRICTED_AGREEMENT),
    });
    await screen.findByRole('heading', { level: 1 });
    const details = within(screen.getByLabelText(en.viewer.details));
    expect(details.getByText(en.documents.category.donor_agreement)).toBeDefined();
    expect(await details.findByText(PROGRAMMES[1]?.name_en ?? '')).toBeDefined();
    expect(details.getByText('2022')).toBeDefined();
    expect(details.getByText(RESTRICTED_AGREEMENT.original_filename)).toBeDefined();
    expect(screen.getByText(en.documents.restricted)).toBeDefined();
    expect(screen.queryByRole('note')).toBeNull();
  });

  it.each([
    ['DOCX', BUDGET_DOCX, en.viewer.convertedWord],
    [
      'TXT',
      makeDocument({
        id: 'd-txt',
        file_type: 'txt',
        is_converted: true,
        original_filename: 'minutes.txt',
      }),
      en.viewer.convertedOther,
    ],
  ])('says page numbers refer to the converted PDF for %s', async (_type, doc, note) => {
    await renderApp({
      path: `/documents/${doc.id}?page=2`,
      user: EN_VIEWER,
      handlers: handlersFor(doc),
    });
    expect((await screen.findByRole('note')).textContent).toBe(note);
  });

  it('works right to left in Arabic, with the same page marked', async () => {
    await renderApp({
      path: `/documents/${BUDGET_DOCX.id}?page=4`,
      user: AR_VIEWER,
      handlers: handlersFor(BUDGET_DOCX),
    });
    await screen.findByRole('group', { name: 'الصفحة 4' });
    expect(document.documentElement.dir).toBe('rtl');
    expect(pageGroup('الصفحة 4').dataset.cited).toBe('true');
    expect(screen.getByRole('note').textContent).toBe(ar.viewer.convertedWord);
    expect(screen.getByText('من 12')).toBeDefined();
  });

  it('keeps the page and makes no GET when the language switches', async () => {
    const actor = userEvent.setup();
    const { calls } = await renderApp({
      path: `/documents/${ANNUAL_REPORT.id}?page=5`,
      user: EN_VIEWER,
      handlers: { ...handlersFor(ANNUAL_REPORT), 'PATCH /api/me': () => json(200, EN_VIEWER) },
    });
    await screen.findByRole('group', { name: 'Page 5' });
    const gets = () => calls.filter((call) => call.method === 'GET').length;
    const before = gets();

    await actor.click(screen.getByRole('button', { name: en.language.switch }));

    expect(await screen.findByRole('group', { name: 'الصفحة 5' })).toBeDefined();
    expect(pageGroup('الصفحة 5').dataset.cited).toBe('true');
    expect(screen.getByLabelText<HTMLInputElement>(ar.viewer.toolbar.pageInput).value).toBe('5');
    expect(gets()).toBe(before);
    expect(pdfMock.opened).toHaveLength(1);
  });

  it('says a document is still being processed instead of opening it', async () => {
    const queued = makeDocument({ id: 'd-queued', status: 'indexing', page_count: null });
    const { calls } = await renderApp({
      path: `/documents/${queued.id}?page=1`,
      user: EN_VIEWER,
      handlers: handlersFor(queued),
    });
    expect(await screen.findByText(en.viewer.notReady)).toBeDefined();
    expect(screen.getByText(en.documents.status.indexing)).toBeDefined();
    expect(calls.some((call) => call.path.endsWith('/file'))).toBe(false);
  });

  it('gives a failed document its reason', async () => {
    await renderApp({
      path: `/documents/${SCANNED_MINUTES.id}`,
      user: EN_VIEWER,
      handlers: handlersFor(SCANNED_MINUTES),
    });
    expect(await screen.findByText(en.viewer.failed)).toBeDefined();
    expect(screen.getByText(en.errors.NO_TEXT_LAYER)).toBeDefined();
  });

  it('shows not found for a document the user may not see', async () => {
    await renderApp({
      path: '/documents/d-hidden?page=2',
      user: EN_VIEWER,
      handlers: { 'GET /api/documents/d-hidden': () => apiError(404, 'NOT_FOUND') },
    });
    expect((await screen.findByRole('alert')).textContent).toBe(en.errors.NOT_FOUND);
  });

  it('translates an error from the file endpoint', async () => {
    await renderApp({
      path: `/documents/${ANNUAL_REPORT.id}?page=2`,
      user: EN_VIEWER,
      handlers: {
        ...handlersFor(ANNUAL_REPORT),
        [`GET /api/documents/${ANNUAL_REPORT.id}/file`]: () => apiError(409, 'DOCUMENT_NOT_READY'),
      },
    });
    expect((await screen.findByRole('alert')).textContent).toBe(en.errors.DOCUMENT_NOT_READY);
  });

  it('says so when pdf.js cannot read the file', async () => {
    pdfMock.fail = true;
    await renderApp({
      path: `/documents/${ANNUAL_REPORT.id}?page=2`,
      user: EN_VIEWER,
      handlers: handlersFor(ANNUAL_REPORT),
    });
    expect((await screen.findByRole('alert')).textContent).toBe(en.viewer.renderFailed);
  });

  it('follows a new ?page= while open', async () => {
    const { router } = await renderApp({
      path: `/documents/${ANNUAL_REPORT.id}?page=2`,
      user: EN_VIEWER,
      handlers: handlersFor(ANNUAL_REPORT),
    });
    await screen.findByRole('group', { name: 'Page 2' });
    await act(() => router.navigate(`/documents/${ANNUAL_REPORT.id}?page=9`));
    await vi.waitFor(() => {
      expect(lastScrolled()).toBe('9');
    });
    expect(pageGroup('Page 9').dataset.cited).toBe('true');
    expect(pageGroup('Page 2').dataset.cited).toBeUndefined();
    expect(pdfMock.opened).toHaveLength(1);
  });
});
