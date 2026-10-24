// F3: multi-file upload against a mocked documents API (B3's contract; see library-mock.ts).
import { expect, type Page, test } from '@playwright/test';

import ar from '../src/locales/ar.json' with { type: 'json' };
import en from '../src/locales/en.json' with { type: 'json' };
import { mockLibrary, signInAs, type UploadOutcome } from './library-mock';

const pdf = (name: string) => ({
  name,
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4 synthetic test file'),
});

const FILES = [
  pdf('annual-report-2021.pdf'),
  { name: 'photo-of-a-page.png', mimeType: 'image/png', buffer: Buffer.from('\x89PNG synthetic') },
  pdf('annual-report-2022.pdf'),
  pdf('board-minutes-2017-scan.pdf'),
  { name: 'board-minutes-2017-11.txt', mimeType: 'text/plain', buffer: Buffer.from('محضر اجتماع') },
];

/** Two bad files: one refused at upload (wrong type), one that fails in processing (a scan). */
function outcome(filename: string): UploadOutcome {
  if (filename.endsWith('.png')) return { reject: { status: 415, code: 'UNSUPPORTED_TYPE' } };
  if (filename.includes('scan')) {
    return {
      steps: ['extracting'],
      failure: { code: 'NO_TEXT_LAYER', params: { pages: 3, scanned_pages: 3 } },
    };
  }
  return { steps: ['extracting', 'indexing', 'ready'] };
}

const fileRow = (page: Page, name: string) => page.locator('li', { hasText: name });

test('five files, two bad: the good ones reach ready and the bad ones say why', async ({
  page,
}) => {
  await signInAs(page, 'editor');
  const api = await mockLibrary(page, {
    role: 'editor',
    documents: [],
    upload: outcome,
    uploadDelayMs: 400,
  });
  await page.goto('/upload?lang=en');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(en.pages.upload.title);

  await page.getByLabel(en.upload.details.category).selectOption('annual_report');
  await page.getByLabel(en.upload.details.year).fill('2021');
  await page.getByLabel(en.upload.drop.choose).setInputFiles(FILES);

  await expect(page.getByRole('listitem')).toHaveCount(5);
  // The two files past the first three wait their turn.
  await expect(fileRow(page, 'board-minutes-2017-11.txt')).toContainText(en.upload.list.waiting);

  await expect(page.getByText('Ready: 3 of 5. Failed: 2.')).toBeVisible({ timeout: 20_000 });
  for (const name of [
    'annual-report-2021.pdf',
    'annual-report-2022.pdf',
    'board-minutes-2017-11.txt',
  ]) {
    await expect(fileRow(page, name)).toContainText(en.documents.status.ready);
    await expect(
      fileRow(page, name).getByRole('link', { name: en.upload.list.open }),
    ).toBeVisible();
  }
  await expect(fileRow(page, 'photo-of-a-page.png')).toContainText(en.errors.UNSUPPORTED_TYPE);
  await expect(fileRow(page, 'board-minutes-2017-scan.pdf')).toContainText(en.errors.NO_TEXT_LAYER);

  // One request per file, three at a time at most, each with the batch details and CSRF header.
  const uploads = api.requests.filter((r) => r.method === 'POST');
  expect(uploads).toHaveLength(5);
  expect(api.maxConcurrentUploads()).toBe(3);
  // Status came from polling by id.
  const polls = api.requests.filter((r) => r.method === 'GET' && r.url.searchParams.has('ids'));
  expect(polls.length).toBeGreaterThan(1);
  expect(polls.every((r) => r.url.searchParams.get('page_size') === '100')).toBe(true);

  // Polling stops once every file has settled.
  const settled = api.requests.length;
  await page.waitForTimeout(3500);
  expect(api.requests.length).toBe(settled);

  // A finished batch survives a language switch, with no GET.
  const gets: string[] = [];
  page.on('request', (req) => {
    if (new URL(req.url()).pathname.startsWith('/api/') && req.method() === 'GET')
      gets.push(req.url());
  });
  await page.getByRole('button', { name: en.language.switch }).click();
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(fileRow(page, 'board-minutes-2017-scan.pdf')).toContainText(ar.errors.NO_TEXT_LAYER);
  await expect(fileRow(page, 'photo-of-a-page.png')).toContainText(ar.errors.UNSUPPORTED_TYPE);
  await expect(fileRow(page, 'annual-report-2021.pdf')).toContainText(ar.documents.status.ready);
  expect(gets).toEqual([]);
});

test('the batch details go with every file, empty ones left out', async ({ page }) => {
  await signInAs(page, 'editor');
  let bodies: string[] = [];
  page.on('request', (req) => {
    if (req.method() === 'POST' && new URL(req.url()).pathname === '/api/documents') {
      bodies = [...bodies, req.postDataBuffer()?.toString('latin1') ?? ''];
    }
  });
  await mockLibrary(page, { role: 'editor', documents: [] });
  await page.goto('/upload?lang=en');
  await page.getByLabel(en.upload.details.restricted).check();
  await page.getByLabel(en.upload.drop.choose).setInputFiles([pdf('budget-2018.pdf')]);
  await expect(page.getByText('Ready: 1 of 1. Failed: 0.')).toBeVisible({ timeout: 15_000 });

  const body = bodies[0] ?? '';
  expect(body).toContain('name="restricted"\r\n\r\ntrue');
  expect(body).toContain('filename="budget-2018.pdf"');
  expect(body).not.toContain('name="year"');
  expect(body).not.toContain('name="category"');
});

test('a duplicate links to the document already in the library', async ({ page }) => {
  await signInAs(page, 'editor');
  await mockLibrary(page, {
    role: 'editor',
    documents: [],
    upload: () => ({
      reject: { status: 409, code: 'DUPLICATE_DOCUMENT', params: { document_id: 'd-existing' } },
    }),
  });
  await page.goto('/upload?lang=ar');
  await page.getByLabel(ar.upload.drop.choose).setInputFiles([pdf('annual-report-2021.pdf')]);
  const item = fileRow(page, 'annual-report-2021.pdf');
  await expect(item).toContainText(ar.errors.DUPLICATE_DOCUMENT);
  await expect(item.getByRole('link', { name: ar.upload.list.openExisting })).toHaveAttribute(
    'href',
    '/documents/d-existing',
  );
});

test('a viewer cannot open the upload screen', async ({ page }) => {
  await signInAs(page, 'viewer');
  await page.goto('/upload?lang=en');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(en.pages.forbidden.title);
});
