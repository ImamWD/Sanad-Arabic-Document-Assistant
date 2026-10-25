// F3: the Library against a mocked documents API (B3's contract; see library-mock.ts).
import { expect, type Page, test } from '@playwright/test';

import ar from '../src/locales/ar.json' with { type: 'json' };
import en from '../src/locales/en.json' with { type: 'json' };
import {
  makeDoc,
  type MockDocument,
  mockLibrary,
  PROGRAMMES,
  seedLibrary,
  signInAs,
} from './library-mock';

const row = (page: Page, doc: MockDocument) => page.locator(`tr[data-document-id="${doc.id}"]`);
const visibleRows = (page: Page) => page.locator('tbody tr');

test('an editor sees every column, the restricted badge, the review flag and failure reasons', async ({
  page,
}) => {
  const docs = seedLibrary();
  await signInAs(page, 'editor');
  await mockLibrary(page, { role: 'editor', documents: Object.values(docs) });
  await page.goto('/library?lang=en');

  await expect(page.getByRole('heading', { level: 1 })).toHaveText(en.pages.library.title);
  await expect(page.getByRole('columnheader')).toHaveText([
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
  // Archived documents stay out unless asked for.
  await expect(visibleRows(page)).toHaveCount(6);

  await expect(row(page, docs.wlpAgreement).getByText(en.documents.restricted)).toBeVisible();
  await expect(row(page, docs.wlpAgreement)).toContainText(PROGRAMMES[1]?.name_en ?? '');
  await expect(row(page, docs.annual2021).getByText(en.documents.restricted)).toHaveCount(0);
  await expect(row(page, docs.gepSurvey).getByText(en.documents.category.none)).toBeVisible();
  await expect(row(page, docs.scannedMinutes)).toContainText(en.documents.status.failed);
  await expect(row(page, docs.scannedMinutes)).toContainText(en.errors.NO_TEXT_LAYER);
  await expect(row(page, docs.budget2018)).toContainText(en.documents.fileType.docx);
});

test('a viewer gets no restricted document, badge, access filter or actions', async ({ page }) => {
  const docs = seedLibrary();
  await signInAs(page, 'viewer');
  await mockLibrary(page, { role: 'viewer', documents: Object.values(docs) });
  await page.goto('/library?lang=en');

  await expect(row(page, docs.annual2021)).toBeVisible();
  await expect(visibleRows(page)).toHaveCount(5);
  await expect(row(page, docs.wlpAgreement)).toHaveCount(0);
  await expect(page.getByText(en.documents.restricted)).toHaveCount(0);
  await expect(page.getByLabel(en.library.filters.access)).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^Actions for/ })).toHaveCount(0);
});

test('filters and search narrow the list, and live in the URL', async ({ page }) => {
  const docs = seedLibrary();
  await signInAs(page, 'editor');
  const api = await mockLibrary(page, { role: 'editor', documents: Object.values(docs) });
  await page.goto('/library?lang=en');
  await expect(visibleRows(page)).toHaveCount(6);
  const lastQuery = () => api.requests.filter((r) => r.method === 'GET').at(-1)?.url.searchParams;

  await page.getByLabel(en.library.filters.category).selectOption('none');
  await expect(visibleRows(page)).toHaveCount(1);
  await expect(row(page, docs.gepSurvey)).toBeVisible();
  expect(lastQuery()?.get('uncategorised')).toBe('true');

  await page.getByLabel(en.library.filters.category).selectOption('budget');
  await page.getByLabel(en.library.filters.fileType).selectOption('docx');
  await expect(visibleRows(page)).toHaveCount(1);
  await expect(row(page, docs.budget2018)).toBeVisible();

  await page.getByRole('button', { name: en.library.filters.clear }).click();
  await page.getByLabel(en.library.filters.yearFrom).fill('2016');
  await page.getByLabel(en.library.filters.yearTo).fill('2018');
  await expect(visibleRows(page)).toHaveCount(3);
  expect(lastQuery()?.get('year_from')).toBe('2016');
  expect(lastQuery()?.get('year_to')).toBe('2018');

  await page.getByRole('button', { name: en.library.filters.clear }).click();
  await page.getByLabel(en.library.filters.status).selectOption('failed');
  await expect(visibleRows(page)).toHaveCount(1);
  await expect(row(page, docs.scannedMinutes)).toBeVisible();

  await page.getByRole('button', { name: en.library.filters.clear }).click();
  await page.getByLabel(en.library.filters.access).selectOption('restricted');
  await expect(visibleRows(page)).toHaveCount(1);
  await expect(row(page, docs.wlpAgreement)).toBeVisible();

  await page.getByRole('button', { name: en.library.filters.clear }).click();
  await page.getByLabel(en.library.filters.programme).selectOption(PROGRAMMES[0]?.id ?? '');
  await expect(visibleRows(page)).toHaveCount(1);
  await expect(row(page, docs.gepSurvey)).toBeVisible();

  await page.getByRole('button', { name: en.library.filters.clear }).click();
  await page.getByLabel(en.library.search.label).fill('annual report');
  await expect(visibleRows(page)).toHaveCount(1);
  await expect(row(page, docs.annual2021)).toBeVisible();
  await expect(page).toHaveURL(/[?&]q=annual\+report/);

  await page.getByLabel(en.library.search.label).fill('');
  await page.getByLabel(en.library.filters.includeArchived).check();
  await expect(visibleRows(page)).toHaveCount(7);
  await expect(row(page, docs.draftBudget).getByText(en.documents.archived)).toBeVisible();

  // The filtered Library survives a reload: the state is in the URL.
  await page.getByLabel(en.library.filters.category).selectOption('budget');
  await expect(visibleRows(page)).toHaveCount(2);
  await page.reload();
  await expect(visibleRows(page)).toHaveCount(2);
  await expect(page.getByLabel(en.library.filters.category)).toHaveValue('budget');
  await expect(page.getByLabel(en.library.filters.includeArchived)).toBeChecked();
});

test('clicking a row opens the viewer', async ({ page }) => {
  const docs = seedLibrary();
  await signInAs(page, 'viewer');
  await mockLibrary(page, { role: 'viewer', documents: Object.values(docs) });
  await page.goto('/library?lang=en');
  await row(page, docs.annual2021).getByRole('cell').nth(3).click();
  await expect(page).toHaveURL(new RegExp(`/documents/${docs.annual2021.id}$`));
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(docs.annual2021.title);
});

test('an editor archives, retries, restricts and edits documents', async ({ page }) => {
  const docs = seedLibrary();
  await signInAs(page, 'editor');
  const api = await mockLibrary(page, { role: 'editor', documents: Object.values(docs) });
  await page.goto('/library?lang=en');
  const actions = (doc: MockDocument) =>
    page.getByRole('button', { name: en.library.actions.menu.replace('{{title}}', doc.title) });
  const choose = async (doc: MockDocument, label: string) => {
    await actions(doc).click();
    await page.getByRole('menuitem', { name: label }).click();
  };

  await choose(docs.annual2016, en.library.actions.archive);
  await expect(row(page, docs.annual2016)).toHaveCount(0);

  await choose(docs.scannedMinutes, en.library.actions.retry);
  await expect(row(page, docs.scannedMinutes)).toContainText(en.documents.status.queued);
  await expect(row(page, docs.scannedMinutes)).not.toContainText(en.errors.NO_TEXT_LAYER);

  await choose(docs.annual2021, en.library.actions.restrict);
  await expect(row(page, docs.annual2021).getByText(en.documents.restricted)).toBeVisible();

  await choose(docs.gepSurvey, en.library.actions.edit);
  const dialog = page.getByRole('dialog', { name: en.library.edit.heading });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel(en.library.edit.category).selectOption('field_survey');
  await dialog.getByRole('button', { name: en.library.edit.save }).click();
  await expect(dialog).toHaveCount(0);
  await expect(row(page, docs.gepSurvey)).toContainText(en.documents.category.field_survey);
  await expect(row(page, docs.gepSurvey).getByText(en.documents.category.none)).toHaveCount(0);

  const writes = api.requests.filter((r) => r.method !== 'GET');
  expect(writes.map((r) => `${r.method} ${r.url.pathname}`)).toEqual([
    `POST /api/documents/${docs.annual2016.id}/archive`,
    `POST /api/documents/${docs.scannedMinutes.id}/retry`,
    `PATCH /api/documents/${docs.annual2021.id}`,
    `PATCH /api/documents/${docs.gepSurvey.id}`,
  ]);
  expect(writes.map((r) => r.body)).toEqual([
    {},
    {},
    { restricted: true },
    { category: 'field_survey' },
  ]);
});

test('in Arabic the table runs right to left, with translated reasons', async ({ page }) => {
  const docs = seedLibrary();
  await signInAs(page, 'editor', 'ar');
  await mockLibrary(page, { role: 'editor', documents: Object.values(docs) });
  await page.goto('/library?lang=ar');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(row(page, docs.scannedMinutes)).toContainText(ar.errors.NO_TEXT_LAYER);
  await expect(row(page, docs.gepSurvey)).toContainText(ar.documents.category.none);

  // The title column sits at the inline start: the right edge in Arabic.
  const title = await page
    .getByRole('columnheader', { name: ar.library.table.title })
    .boundingBox();
  const status = await page
    .getByRole('columnheader', { name: ar.library.table.status })
    .boundingBox();
  if (!title || !status) throw new Error('table not rendered');
  expect(title.x).toBeGreaterThan(status.x);
});

test('switching language keeps the filters and the rows, and makes no GET', async ({ page }) => {
  const docs = seedLibrary();
  await signInAs(page, 'editor');
  await mockLibrary(page, { role: 'editor', documents: Object.values(docs) });
  await page.goto('/library?lang=en&category=donor_agreement');
  await expect(visibleRows(page)).toHaveCount(1);

  const gets: string[] = [];
  page.on('request', (req) => {
    if (new URL(req.url()).pathname.startsWith('/api/') && req.method() === 'GET')
      gets.push(req.url());
  });
  await page.getByRole('button', { name: en.language.switch }).click();

  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(ar.pages.library.title);
  await expect(page.getByLabel(ar.library.filters.category)).toHaveValue('donor_agreement');
  await expect(row(page, docs.wlpAgreement)).toContainText(PROGRAMMES[1]?.name_ar ?? '');
  await expect(row(page, docs.wlpAgreement)).toContainText(ar.documents.restricted);
  expect(gets).toEqual([]);
});

test('a code inside an Arabic title never breaks across lines, at any width', async ({ page }) => {
  // A line break at the hyphen put "(-WASH" on one line and "(2018-01" on the next.
  const wash = makeDoc({
    title: 'التقييم النهائي لمشروع المياه والإصحاح البيئي في قرى الهضبة الشرقية (WASH-2018-01)',
    original_filename: 'wash-final-evaluation-2021.pdf',
    category: 'programme_evaluation',
  });
  await signInAs(page, 'viewer');
  await mockLibrary(page, { role: 'viewer', documents: [wash] });
  await page.goto('/library?lang=en');
  const code = row(page, wash).locator('bdi', { hasText: 'WASH-2018-01' });
  await expect(code).toHaveText('WASH-2018-01');
  for (let width = 700; width <= 1100; width += 10) {
    await page.setViewportSize({ width, height: 900 });
    const lines = await code.evaluate((el) => el.getClientRects().length);
    expect(lines, `at ${String(width)} px`).toBe(1);
  }
});
