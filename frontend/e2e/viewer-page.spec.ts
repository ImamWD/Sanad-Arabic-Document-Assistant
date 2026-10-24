// F4: the pdf.js viewer, for real in Chromium, behind the real nginx CSP. The documents API is
// mocked (B3's contract) and serves a generated multi-page PDF (see library-mock.ts).
import { expect, type Page, test } from '@playwright/test';

import ar from '../src/locales/ar.json' with { type: 'json' };
import en from '../src/locales/en.json' with { type: 'json' };
import { makeDoc, mockDocument, signInAs, watchProblems } from './library-mock';

const REPORT = makeDoc({ title: 'Annual Report 2021', page_count: 12 });
const BUDGET = makeDoc({
  title: 'الموازنة التقديرية لعام 2018',
  file_type: 'docx',
  category: 'budget',
  year: 2018,
  page_count: 4,
});

const pageGroup = (page: Page, label: string) =>
  page.getByRole('group', { name: label, exact: true });

test('opens at ?page=N, scrolled to that page, drawn and marked as cited', async ({ page }) => {
  const problems = await watchProblems(page);
  const assets: string[] = [];
  page.on('request', (req) => {
    const url = new URL(req.url());
    if (url.pathname.startsWith('/assets/')) assets.push(url.pathname);
  });
  await signInAs(page, 'viewer');
  await mockDocument(page, REPORT);
  await page.goto(`/documents/${REPORT.id}?page=7&lang=en`);

  await expect(page.getByRole('heading', { level: 1 })).toHaveText(REPORT.title);
  const cited = pageGroup(page, 'Page 7');
  await expect(cited).toHaveAttribute('aria-current', 'true');
  await expect(cited).toHaveAttribute('data-rendered', 'true');
  await expect(cited).toBeInViewport();
  await expect(cited.getByText(en.viewer.citedPage)).toBeVisible();
  await expect(page.locator('[data-cited]')).toHaveCount(1);
  await expect(page.getByLabel(en.viewer.toolbar.pageInput)).toHaveValue('7');
  await expect(page.getByText('of 12')).toBeVisible();

  // The canvas really holds a drawn page (not blank): the grey band at the top.
  const painted = await cited.locator('canvas').evaluate((canvas: HTMLCanvasElement) => {
    const context = canvas.getContext('2d');
    if (!context || canvas.width === 0) return false;
    const { data } = context.getImageData(0, 0, canvas.width, Math.ceil(canvas.height / 10));
    for (let i = 0; i < data.length; i += 4) if ((data[i] ?? 255) < 240) return true;
    return false;
  });
  expect(painted).toBe(true);

  // Pages far from the viewport are not drawn (long documents stay light).
  await expect(pageGroup(page, 'Page 1')).not.toHaveAttribute('data-rendered', 'true');

  // pdf.js and its worker are same-origin bundle assets, and nothing broke the CSP.
  expect(assets.some((path) => /^\/assets\/pdf\.worker[^/]*\.js$/.test(path))).toBe(true);
  expect(await problems()).toEqual([]);
});

test('the toolbar moves between pages', async ({ page }) => {
  await signInAs(page, 'viewer');
  await mockDocument(page, REPORT);
  await page.goto(`/documents/${REPORT.id}?page=3&lang=en`);
  await expect(pageGroup(page, 'Page 3')).toBeInViewport();

  await page.getByRole('button', { name: en.viewer.toolbar.next }).click();
  await expect(pageGroup(page, 'Page 4')).toBeInViewport();
  await expect(page.getByLabel(en.viewer.toolbar.pageInput)).toHaveValue('4');

  await page.getByLabel(en.viewer.toolbar.pageInput).fill('11');
  await page.getByLabel(en.viewer.toolbar.pageInput).press('Enter');
  await expect(pageGroup(page, 'Page 11')).toBeInViewport();
  await expect(pageGroup(page, 'Page 11')).toHaveAttribute('data-rendered', 'true');

  await page
    .getByRole('button', { name: en.viewer.toolbar.goToCited.replace('{{page}}', '3') })
    .click();
  await expect(pageGroup(page, 'Page 3')).toBeInViewport();
  await expect(page.getByLabel(en.viewer.toolbar.pageInput)).toHaveValue('3');
});

test('a converted Word file says its page numbers are the PDF’s', async ({ page }) => {
  await signInAs(page, 'viewer');
  await mockDocument(page, BUDGET);
  await page.goto(`/documents/${BUDGET.id}?page=2&lang=en`);
  await expect(page.getByRole('note')).toHaveText(en.viewer.convertedWord);
  await expect(pageGroup(page, 'Page 2')).toHaveAttribute('aria-current', 'true');
});

test('in Arabic the chrome mirrors, the page does not', async ({ page }) => {
  const problems = await watchProblems(page);
  await signInAs(page, 'viewer', 'ar');
  await mockDocument(page, BUDGET);
  await page.goto(`/documents/${BUDGET.id}?page=3&lang=ar`);

  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  const cited = pageGroup(page, 'الصفحة 3');
  await expect(cited).toHaveAttribute('aria-current', 'true');
  await expect(cited).toHaveAttribute('data-rendered', 'true');
  await expect(cited).toBeInViewport();
  await expect(page.getByRole('note')).toHaveText(ar.viewer.convertedWord);

  // "Previous" sits at the inline start: right of "Next" in Arabic.
  const previous = await page
    .getByRole('button', { name: ar.viewer.toolbar.previous })
    .boundingBox();
  const next = await page.getByRole('button', { name: ar.viewer.toolbar.next }).boundingBox();
  if (!previous || !next) throw new Error('toolbar not rendered');
  expect(previous.x).toBeGreaterThan(next.x);

  // The canvas itself is never flipped.
  const transform = await cited.locator('canvas').evaluate((el) => getComputedStyle(el).transform);
  expect(transform).toBe('none');
  expect(await problems()).toEqual([]);
});

test('switching language keeps the page in view and makes no GET', async ({ page }) => {
  await signInAs(page, 'viewer');
  await mockDocument(page, REPORT);
  await page.goto(`/documents/${REPORT.id}?page=9&lang=en`);
  await expect(pageGroup(page, 'Page 9')).toHaveAttribute('data-rendered', 'true');
  await expect(pageGroup(page, 'Page 9')).toBeInViewport();

  const gets: string[] = [];
  page.on('request', (req) => {
    if (new URL(req.url()).pathname.startsWith('/api/') && req.method() === 'GET')
      gets.push(req.url());
  });
  await page.getByRole('button', { name: en.language.switch }).click();

  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  const cited = pageGroup(page, 'الصفحة 9');
  await expect(cited).toHaveAttribute('aria-current', 'true');
  await expect(cited).toBeInViewport();
  await expect(page.getByLabel(ar.viewer.toolbar.pageInput)).toHaveValue('9');
  expect(gets).toEqual([]);
});

test('a document still being processed is not opened', async ({ page }) => {
  const queued = makeDoc({ title: 'Annual Report 2022', status: 'indexing', page_count: null });
  await signInAs(page, 'viewer');
  await mockDocument(page, queued);
  await page.goto(`/documents/${queued.id}?page=2&lang=en`);
  await expect(page.getByText(en.viewer.notReady)).toBeVisible();
  await expect(page.getByText(en.documents.status.indexing)).toBeVisible();
  await expect(page.locator('canvas')).toHaveCount(0);
});
