// F2: the finished answer. POST /api/ask/stream is answered by page.route with the whole event
// stream at once (R1 serves it later), and GET /api/queries likewise.
import { expect, type Page, test } from '@playwright/test';

import ar from '../src/locales/ar.json' with { type: 'json' };
import en from '../src/locales/en.json' with { type: 'json' };
import {
  ANSWER,
  ask,
  DOCX_CITATION,
  FINAL_ANSWERED,
  FINAL_LOW_CONFIDENCE,
  GUEST,
  mockFullStream,
  PDF_CITATION,
  QUERY_ID,
  QUESTION,
  signIn,
} from './ask-mock';

const ANSWER_EVENTS: [string, unknown][] = [
  ['stage', { stage: 'searching' }],
  ['stage', { stage: 'reading', sources: 2, band: 'answer' }],
  ['eta', { expected_seconds: 12 }],
  ['stage', { stage: 'writing' }],
  ['token', { text: 'In 2021 the programme enrolled' }],
  ['final', FINAL_ANSWERED],
];

const card = (page: Page, title: string) =>
  page.getByRole('link').filter({ has: page.getByText(title, { exact: true }) });

async function saveScreenshot(page: Page, name: string) {
  const info = test.info();
  const path = info.outputPath(`${name}.png`);
  await page.screenshot({ path, fullPage: true });
  await info.attach(name, { path, contentType: 'image/png' });
}

test('sends the question as JSON with the CSRF header and renders the final answer', async ({
  page,
}) => {
  await signIn(page);
  await mockFullStream(page, ANSWER_EVENTS);
  await page.goto('/ask?lang=en');

  const request = page.waitForRequest('**/api/ask/stream');
  await ask(page, en.ask.form.label);
  const sent = await request;
  expect(sent.method()).toBe('POST');
  expect(sent.headers()['x-sanad']).toBe('1');
  expect(sent.headers()['content-type']).toBe('application/json');
  expect(sent.headers().accept).toBe('text/event-stream');
  expect(sent.postDataJSON()).toEqual({ question: QUESTION });

  await expect(page.getByRole('heading', { level: 2, name: QUESTION })).toBeVisible();
  await expect(page.getByText(ANSWER, { exact: true })).toBeVisible();
  await expect(page.getByText('In 2021 the programme enrolled', { exact: true })).toHaveCount(0);
  const sources = page.getByRole('region', { name: en.ask.citations.heading });
  await expect(sources.getByRole('link')).toHaveCount(2);
  await expect(card(page, PDF_CITATION.title)).toContainText(
    en.ask.citations.page.replace('{{page}}', '7'),
  );
  await expect(card(page, PDF_CITATION.title)).toContainText(PDF_CITATION.snippet);
  await expect(page.getByRole('status')).toHaveCount(0);
});

for (const [lang, messages, dir] of [
  ['en', en, 'ltr'],
  ['ar', ar, 'rtl'],
] as const) {
  test(`a Word citation notes the converted PDF and a PDF citation does not (${lang})`, async ({
    page,
  }) => {
    await signIn(page);
    await mockFullStream(page, ANSWER_EVENTS);
    await page.goto(`/ask?lang=${lang}`);
    await expect(page.locator('html')).toHaveAttribute('dir', dir);
    await ask(page, messages.ask.form.label);

    await expect(card(page, DOCX_CITATION.title)).toContainText(
      messages.ask.citations.convertedWord,
    );
    await expect(card(page, PDF_CITATION.title)).not.toContainText(
      messages.ask.citations.convertedWord,
    );
    await expect(card(page, PDF_CITATION.title)).not.toContainText(
      messages.ask.citations.convertedOther,
    );
    // Titles and snippets take their own direction, whatever the page's.
    await expect(page.getByText(DOCX_CITATION.title, { exact: true })).toHaveAttribute(
      'dir',
      'auto',
    );
    await saveScreenshot(page, `ask-answer-${lang}`);
  });
}

test('a citation card opens the viewer at its page', async ({ page }) => {
  await signIn(page);
  await mockFullStream(page, ANSWER_EVENTS);
  await page.goto('/ask?lang=en');
  await ask(page, en.ask.form.label);

  await card(page, DOCX_CITATION.title).click();
  await expect(page).toHaveURL(new RegExp(`/documents/${DOCX_CITATION.document_id}\\?page=3$`));
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(en.pages.document.title);
});

test('switching language keeps the shown answer, mirrors it and makes no GET', async ({ page }) => {
  await signIn(page);
  await mockFullStream(page, [
    ['stage', { stage: 'reading', sources: 2, band: 'low_confidence' }],
    ['final', FINAL_LOW_CONFIDENCE],
  ]);
  await page.goto('/ask?lang=en');
  await ask(page, en.ask.form.label);
  await expect(page.getByText(ANSWER, { exact: true })).toBeVisible();

  const gets: string[] = [];
  page.on('request', (req) => {
    if (new URL(req.url()).pathname.startsWith('/api/') && req.method() === 'GET') {
      gets.push(req.url());
    }
  });
  await page.getByRole('button', { name: en.language.switch }).click();

  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(ar.pages.ask.title);
  await expect(page.getByRole('heading', { level: 2, name: QUESTION })).toBeVisible();
  await expect(page.getByText(ANSWER, { exact: true })).toBeVisible();
  await expect(page.getByRole('note')).toHaveText(ar.answer.lowConfidence);
  await expect(card(page, DOCX_CITATION.title)).toContainText(ar.ask.citations.convertedWord);
  await expect(page).toHaveURL(/\/ask/);

  // The banner's thick edge is at the inline start: left in English, right in Arabic.
  const edge = (side: 'left' | 'right') =>
    page
      .getByRole('note')
      .evaluate((el, s) => getComputedStyle(el).getPropertyValue(`border-${s}-width`), side);
  expect(await edge('right')).toBe('6px');
  expect(await edge('left')).toBe('1px');
  expect(gets).toEqual([]);
});

test('the history panel loads when opened and shows a stored answer', async ({ page }) => {
  await signIn(page);
  const history = [
    {
      id: QUERY_ID,
      question: 'ما عدد الفتيات المسجلات في عام 2021؟',
      outcome: 'answered',
      created_at: '2026-10-20T09:30:00Z',
    },
    {
      id: '3f0b8c4e-1d2a-4e6f-9a7b-000000000102',
      question: 'What did the board decide about the 2024 budget?',
      outcome: 'no_answer',
      created_at: '2026-10-19T14:05:00Z',
    },
  ];
  const listed: string[] = [];
  await page.route('**/api/queries', async (route) => {
    listed.push(route.request().method());
    await route.fulfill({ json: history });
  });
  await page.route(`**/api/queries/${QUERY_ID}`, (route) =>
    route.fulfill({
      json: {
        ...FINAL_ANSWERED,
        id: QUERY_ID,
        question: history[0]?.question,
        created_at: history[0]?.created_at,
      },
    }),
  );
  await page.goto('/ask?lang=ar');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(ar.pages.ask.title);
  expect(listed).toEqual([]);

  await page.getByRole('button', { name: ar.ask.history.toggle }).click();
  const panel = page.getByRole('complementary', { name: ar.ask.history.heading });
  await expect(panel.getByRole('button')).toHaveCount(2);
  await expect(panel.getByText(ar.ask.outcome.no_answer)).toBeVisible();

  // The panel is at the inline end: left of the question box in Arabic.
  const panelBox = await panel.boundingBox();
  const formBox = await page.getByRole('textbox', { name: ar.ask.form.label }).boundingBox();
  if (!panelBox || !formBox) throw new Error('layout not rendered');
  expect(panelBox.x).toBeLessThan(formBox.x);

  await panel.getByRole('button').first().click();
  await expect(
    page.getByRole('heading', { level: 2, name: history[0]?.question ?? '' }),
  ).toBeVisible();
  await expect(page.getByText(ANSWER, { exact: true })).toBeVisible();
  await expect(card(page, PDF_CITATION.title)).toBeVisible();
  await saveScreenshot(page, 'ask-history-ar');
});

test('the guest goes from the login page to a cited page in three clicks', async ({ page }) => {
  let user: object | null = null;
  await page.route('**/api/me', (route) =>
    user
      ? route.fulfill({ json: user })
      : route.fulfill({ status: 401, json: { error: { code: 'UNAUTHENTICATED', params: {} } } }),
  );
  await page.route('**/api/auth/guest', async (route) => {
    user = GUEST;
    await route.fulfill({ json: GUEST });
  });
  await mockFullStream(page, ANSWER_EVENTS);
  await page.goto('/login?lang=en');

  await page.getByRole('button', { name: en.auth.login.guest }).click(); // 1
  await expect(page).toHaveURL(/\/ask$/);
  await expect(page.getByRole('button', { name: en.ask.history.toggle })).toBeVisible();
  await page.getByRole('textbox', { name: en.ask.form.label }).click(); // 2
  await page.keyboard.type(QUESTION);
  await page.keyboard.press('Enter');
  await card(page, PDF_CITATION.title).click(); // 3
  await expect(page).toHaveURL(new RegExp(`/documents/${PDF_CITATION.document_id}\\?page=7$`));
});
