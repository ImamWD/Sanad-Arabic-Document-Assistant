// F2 test helpers: a signed-in user, synthetic Ask payloads, and two ways to fake
// POST /api/ask/stream until R1 serves it.
//   mockFullStream: page.route answers with the whole event stream at once. Good for the
//     request shape and the final render.
//   controlStream: route.fulfill can't deliver a body in pieces, so a slow stream is faked by
//     a fetch shim (addInitScript) that hands the page a ReadableStream; the test sends each
//     event when it wants, and checks the screen in between.
// Users and figures are synthetic and obviously fake; titles come from the seed corpus.
import type { Page } from '@playwright/test';

export const VIEWER = {
  id: '00000000-0000-4000-8000-000000000001',
  name: 'ليلى تجريبية',
  email: 'viewer@example.org',
  role: 'viewer',
  preferred_language: 'en',
  is_guest: false,
};
export const GUEST = { ...VIEWER, name: 'ضيف تجريبي', email: '', is_guest: true };

export const QUESTION = 'How many girls enrolled in the programme in 2021?';
export const QUERY_ID = '3f0b8c4e-1d2a-4e6f-9a7b-000000000101';

export const PDF_CITATION = {
  rank: 1,
  document_id: 'd1a2b3c4-0000-4000-8000-000000002021',
  title: 'Annual Report 2021',
  page_number: 7,
  snippet:
    "In 2021 the Girls' Basic Education Support Programme enrolled 1,240 girls in 18 schools.",
  char_start: 120,
  char_end: 214,
  file_type: 'pdf',
  is_converted: false,
};

export const DOCX_CITATION = {
  rank: 2,
  document_id: 'd1a2b3c4-0000-4000-8000-000000002018',
  title: 'الموازنة التقديرية لعام 2018',
  page_number: 3,
  snippet: 'خُصص مبلغ 85,000 دولار لبرنامج دعم التعليم الأساسي للفتيات.',
  char_start: 40,
  char_end: 98,
  file_type: 'docx',
  is_converted: true,
};

export const ANSWER =
  'In 2021 the programme enrolled 1,240 girls [1]. The 2018 budget set aside USD 85,000 for it [2].';

export const FINAL_ANSWERED = {
  query_id: QUERY_ID,
  outcome: 'answered',
  band: 'answer',
  refusal_reason: null,
  answer: ANSWER,
  citations: [PDF_CITATION, DOCX_CITATION],
  nearest_documents: [],
};

export const FINAL_LOW_CONFIDENCE = {
  ...FINAL_ANSWERED,
  outcome: 'low_confidence',
  band: 'low_confidence',
};

export const NEAREST = [
  { document_id: 'd1a2b3c4-0000-4000-8000-000000003001', title: 'Annual Report 2023' },
  { document_id: 'd1a2b3c4-0000-4000-8000-000000003002', title: 'التقرير السنوي 2022' },
  { document_id: 'd1a2b3c4-0000-4000-8000-000000003003', title: 'Annual Report 2016' },
];

export const FINAL_GATE = {
  query_id: QUERY_ID,
  outcome: 'no_answer',
  band: 'refuse',
  refusal_reason: 'gate',
  answer: null,
  citations: [],
  nearest_documents: NEAREST,
};

export const FINAL_SENTINEL = {
  ...FINAL_GATE,
  band: 'answer',
  refusal_reason: 'sentinel',
  nearest_documents: [],
};

export function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/** GET /api/me answers with `user`; PATCH /api/me (the saved language) is accepted. */
export async function signIn(page: Page, user: object = VIEWER) {
  await page.route('**/api/me', (route) =>
    route.request().method() === 'PATCH'
      ? route.fulfill({ status: 204 })
      : route.fulfill({ json: user }),
  );
}

/** Answer POST /api/ask/stream with these events, all in one response. */
export async function mockFullStream(page: Page, events: [string, unknown][]) {
  await page.route('**/api/ask/stream', (route) =>
    route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
      body: events.map(([event, data]) => sse(event, data)).join(''),
    }),
  );
}

interface StreamControl {
  requests: { body: string; headers: Record<string, string> }[];
  send(text: string): void;
  close(): void;
}

declare global {
  interface Window {
    __sanadAskStream?: StreamControl;
  }
}

/** Fake POST /api/ask/stream with a stream the test feeds through `send`. */
export async function controlStream(page: Page) {
  await page.addInitScript(() => {
    const realFetch = window.fetch.bind(window);
    const encoder = new TextEncoder();
    let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
    const control: StreamControl = {
      requests: [],
      send(text) {
        controller?.enqueue(encoder.encode(text));
      },
      close() {
        controller?.close();
      },
    };
    window.__sanadAskStream = control;
    window.fetch = (input, init) => {
      const url = input instanceof Request ? input.url : String(input);
      if (new URL(url, window.location.href).pathname !== '/api/ask/stream') {
        return realFetch(input, init);
      }
      const headers: Record<string, string> = {};
      new Headers(init?.headers).forEach((value, key) => {
        headers[key] = value;
      });
      control.requests.push({ body: typeof init?.body === 'string' ? init.body : '', headers });
      const body = new ReadableStream<Uint8Array>({
        start(c) {
          controller = c;
        },
      });
      return Promise.resolve(
        new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }),
      );
    };
  });

  return {
    send: (event: string, data: unknown) =>
      page.evaluate((text) => window.__sanadAskStream?.send(text), sse(event, data)),
    close: () => page.evaluate(() => window.__sanadAskStream?.close()),
    requests: () => page.evaluate(() => window.__sanadAskStream?.requests ?? []),
  };
}

/** Type a question in the box and press Enter. */
export async function ask(page: Page, label: string, question = QUESTION) {
  const box = page.getByRole('textbox', { name: label });
  await box.fill(question);
  await box.press('Enter');
}
