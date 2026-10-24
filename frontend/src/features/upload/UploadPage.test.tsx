import { act, cleanup, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { json, renderApp, testUser } from '../../app/test-utils';
import { AR_NUMBERING } from '../../lib/config';
import { createFormat } from '../../lib/format';
import ar from '../../locales/ar.json';
import en from '../../locales/en.json';
import { makeDocument, PROGRAMMES } from '../library/test-fixtures';
import type { DocumentItem } from '../library/types';

const EN_EDITOR = testUser('editor', { preferred_language: 'en' });

/** A stand-in for XMLHttpRequest: the test answers each upload when it wants. */
class FakeXhr {
  static all: FakeXhr[] = [];
  static open = () => FakeXhr.all.filter((xhr) => xhr.status === 0);

  upload: { onprogress: ((event: Partial<ProgressEvent>) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  status = 0;
  responseText = '';
  method = '';
  url = '';
  headers: Record<string, string> = {};
  body: FormData | null = null;

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }
  send(body: FormData) {
    this.body = body;
    FakeXhr.all.push(this);
  }
  abort() {
    this.onabort?.();
  }

  get fileName(): string {
    return (this.body?.get('file') as File).name;
  }
  progress(loaded: number, total: number) {
    this.upload.onprogress?.({ lengthComputable: true, loaded, total });
  }
  respond(status: number, body: unknown) {
    this.status = status;
    this.responseText = JSON.stringify(body);
    this.onload?.();
  }
}

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, '', '/');
  FakeXhr.all = [];
  vi.stubGlobal('XMLHttpRequest', FakeXhr);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const pdf = (name: string) => new File(['%PDF-1.7 synthetic'], name, { type: 'application/pdf' });

function docFor(name: string, id: string, overrides: Partial<DocumentItem> = {}): DocumentItem {
  return makeDocument({
    id,
    title: name.replace(/\.\w+$/, ''),
    original_filename: name,
    status: 'queued',
    page_count: null,
    ...overrides,
  });
}

/** The row of the upload list for this file name. */
function rowOf(name: string): HTMLElement {
  const row = screen.getByText(name).closest('li');
  if (!row) throw new Error(`no row for ${name}`);
  return row;
}

describe('upload', () => {
  it('uploads five files three at a time; the good ones reach ready, the bad ones say why', async () => {
    const actor = userEvent.setup({ applyAccept: false });
    // What the "server" holds once a file is accepted; the poll returns its current state.
    const server = new Map<string, DocumentItem>();
    const { calls } = await renderApp({
      path: '/upload',
      user: EN_EDITOR,
      handlers: {
        'GET /api/programmes': () => json(200, PROGRAMMES),
        'GET /api/documents': () =>
          json(200, { items: [...server.values()], total: server.size, page: 1, page_size: 100 }),
      },
    });
    await screen.findByRole('heading', { name: en.pages.upload.title });

    await actor.selectOptions(screen.getByLabelText(en.upload.details.category), 'annual_report');
    await actor.type(screen.getByLabelText(en.upload.details.year), '2021');
    await actor.upload(screen.getByLabelText(en.upload.drop.choose), [
      pdf('annual-report-2021.pdf'),
      new File(['\x89PNG'], 'photo-of-a-page.png', { type: 'image/png' }),
      pdf('annual-report-2022.pdf'),
      pdf('board-minutes-2017-scan.pdf'),
      new File(['محضر'], 'board-minutes-2017-11.txt', { type: 'text/plain' }),
    ]);

    // Three requests at once; the other two wait their turn.
    expect(FakeXhr.open().map((xhr) => xhr.fileName)).toEqual([
      'annual-report-2021.pdf',
      'photo-of-a-page.png',
      'annual-report-2022.pdf',
    ]);
    expect(
      within(rowOf('board-minutes-2017-scan.pdf')).getByText(en.upload.list.waiting),
    ).toBeDefined();
    const first = FakeXhr.all[0];
    expect(first?.method).toBe('POST');
    expect(first?.url).toBe('/api/documents');
    expect(first?.headers['X-Sanad']).toBe('1');
    expect(first?.body?.get('category')).toBe('annual_report');
    expect(first?.body?.get('year')).toBe('2021');
    expect(first?.body?.has('programme_id')).toBe(false);

    act(() => {
      first?.progress(50, 100);
    });
    expect(within(rowOf('annual-report-2021.pdf')).getByText('Uploading 50%')).toBeDefined();

    // A bad file is refused at upload; its slot goes to the next file.
    act(() => {
      FakeXhr.all[1]?.respond(415, { error: { code: 'UNSUPPORTED_TYPE', params: {} } });
    });
    await vi.waitFor(() => {
      expect(FakeXhr.open()).toHaveLength(3);
    });

    const accept = async (xhr: FakeXhr | undefined, id: string, ready: Partial<DocumentItem>) => {
      if (!xhr) throw new Error('no such upload');
      const doc = docFor(xhr.fileName, id);
      await act(async () => {
        xhr.respond(201, doc);
        server.set(id, { ...doc, ...ready });
        await Promise.resolve();
      });
    };
    const READY = { status: 'ready', page_count: 12 } as const;
    await accept(FakeXhr.all[0], 'd-1', READY);
    await accept(FakeXhr.all[2], 'd-2', READY);
    await vi.waitFor(() => {
      expect(FakeXhr.all).toHaveLength(5);
    });
    expect(FakeXhr.open().length).toBeLessThanOrEqual(3);
    await accept(FakeXhr.all[3], 'd-3', {
      status: 'failed',
      error_code: 'NO_TEXT_LAYER',
      error_params: { pages: 3, scanned_pages: 3 },
    });
    await accept(FakeXhr.all[4], 'd-4', READY);

    await vi.waitFor(() => {
      expect(screen.getByText('Ready: 3 of 5. Failed: 2.')).toBeDefined();
    });
    for (const name of [
      'annual-report-2021.pdf',
      'annual-report-2022.pdf',
      'board-minutes-2017-11.txt',
    ]) {
      const row = within(rowOf(name));
      expect(row.getByText(en.documents.status.ready)).toBeDefined();
      expect(row.getByRole('link', { name: en.upload.list.open })).toBeDefined();
    }
    expect(
      within(rowOf('photo-of-a-page.png')).getByText(en.errors.UNSUPPORTED_TYPE),
    ).toBeDefined();
    expect(
      within(rowOf('board-minutes-2017-scan.pdf')).getByText(en.errors.NO_TEXT_LAYER),
    ).toBeDefined();

    // The processing states came from polling GET /api/documents.
    const polls = calls.filter((call) => call.method === 'GET' && call.path === '/api/documents');
    expect(polls.length).toBeGreaterThan(0);
  });

  it('links a duplicate to the document already in the library', async () => {
    const actor = userEvent.setup();
    await renderApp({
      path: '/upload',
      user: EN_EDITOR,
      handlers: { 'GET /api/programmes': () => json(200, PROGRAMMES) },
    });
    await actor.upload(await screen.findByLabelText(en.upload.drop.choose), pdf('budget-2018.pdf'));
    act(() => {
      FakeXhr.all[0]?.respond(409, {
        error: { code: 'DUPLICATE_DOCUMENT', params: { document_id: 'd-existing' } },
      });
    });
    const row = within(rowOf('budget-2018.pdf'));
    expect(await row.findByText(en.errors.DUPLICATE_DOCUMENT)).toBeDefined();
    expect(row.getByRole('link', { name: en.upload.list.openExisting }).getAttribute('href')).toBe(
      '/documents/d-existing',
    );
  });

  it('holds new files back while the year is not a valid year', async () => {
    const actor = userEvent.setup();
    await renderApp({
      path: '/upload',
      user: EN_EDITOR,
      handlers: { 'GET /api/programmes': () => json(200, PROGRAMMES) },
    });
    await actor.type(await screen.findByLabelText(en.upload.details.year), '21');
    expect(screen.getByRole('alert').textContent).toBe(
      en.library.edit.yearInvalid.replace('{{min}}', '1900').replace('{{max}}', '2100'),
    );
    expect(screen.getByLabelText<HTMLInputElement>(en.upload.drop.choose).disabled).toBe(true);
  });

  it('keeps the list and makes no GET when the language switches', async () => {
    const actor = userEvent.setup();
    const { calls } = await renderApp({
      path: '/upload',
      user: EN_EDITOR,
      handlers: {
        'GET /api/programmes': () => json(200, PROGRAMMES),
        'PATCH /api/me': () => json(200, EN_EDITOR),
      },
    });
    await actor.upload(await screen.findByLabelText(en.upload.drop.choose), pdf('budget-2018.pdf'));
    act(() => {
      FakeXhr.all[0]?.progress(1, 4);
    });
    const gets = () => calls.filter((call) => call.method === 'GET').length;
    const before = gets();

    await actor.click(screen.getByRole('button', { name: en.language.switch }));

    expect(await screen.findByRole('heading', { name: ar.pages.upload.title })).toBeDefined();
    const percent = createFormat('ar', AR_NUMBERING).percent(0.25);
    expect(
      within(rowOf('budget-2018.pdf')).getByText(
        ar.upload.list.uploading.replace('{{percent}}', percent),
      ),
    ).toBeDefined();
    expect(gets()).toBe(before);
  });
});
