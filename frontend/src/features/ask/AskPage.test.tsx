import { act, cleanup, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { apiError, GUEST, json, renderApp, testUser } from '../../app/test-utils';
import { sessionQueryKey } from '../auth/session';
import type { Me } from '../auth/types';
import ar from '../../locales/ar.json';
import en from '../../locales/en.json';
import {
  ANSWER_TEXT,
  DOCX_CITATION,
  FINAL_ANSWERED,
  FINAL_GATE,
  FINAL_LOW_CONFIDENCE,
  FINAL_SENTINEL,
  fakeStream,
  NEAREST,
  PDF_CITATION,
  QUERY_ID,
  TXT_CITATION,
} from './test-fixtures';

const EN_VIEWER = testUser('viewer', { preferred_language: 'en' });
const AR_VIEWER = testUser('viewer', { preferred_language: 'ar' });
const QUESTION = 'How many girls enrolled in the programme in 2021?';

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, '', '/');
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

/** "{{name}}" placeholders filled in, to compare with what the screen shows. */
function fill(template: string, values: Record<string, string>): string {
  return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) => values[name] ?? '');
}

/** Each POST /api/ask/stream gets a fresh stream; `current` is the latest. */
function streams() {
  const all: ReturnType<typeof fakeStream>[] = [];
  return {
    all,
    handler: () => {
      const stream = fakeStream();
      all.push(stream);
      return stream.response();
    },
    get current() {
      const stream = all.at(-1);
      if (!stream) throw new Error('no question was sent');
      return stream;
    },
  };
}

async function openAsk(user: Me = EN_VIEWER, handlers: Parameters<typeof renderApp>[0] = {}) {
  const asks = streams();
  const messages = user.preferred_language === 'ar' ? ar : en;
  const view = await renderApp({
    path: '/ask',
    user,
    ...handlers,
    handlers: { 'POST /api/ask/stream': asks.handler, ...handlers.handlers },
  });
  await screen.findByRole('heading', { level: 1, name: messages.pages.ask.title });
  const actor = userEvent.setup();

  /** Send one server event and let the stream reader hand it to the screen. */
  const send = async (event: string, data: unknown) => {
    await act(async () => {
      asks.current.send(event, data);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  };
  const ask = async (question = QUESTION) => {
    await actor.type(screen.getByRole('textbox', { name: messages.ask.form.label }), question);
    await actor.keyboard('{Enter}');
  };
  return { ...view, actor, asks, send, ask, messages };
}

const status = () => screen.getByRole('status');
const gets = (calls: { method: string; path: string }[]) => calls.filter((c) => c.method === 'GET');

describe('question box', () => {
  it('Enter sends the question, Shift+Enter adds a new line', async () => {
    const { actor, calls, messages } = await openAsk();
    const box = screen.getByRole('textbox', { name: messages.ask.form.label });
    await actor.type(box, 'First line{Shift>}{Enter}{/Shift}second line');
    expect(box).toHaveProperty('value', 'First line\nsecond line');
    expect(calls.filter((c) => c.path === '/api/ask/stream')).toEqual([]);

    await actor.keyboard('{Enter}');
    expect(calls.filter((c) => c.path === '/api/ask/stream')).toEqual([
      { method: 'POST', path: '/api/ask/stream', body: { question: 'First line\nsecond line' } },
    ]);
    expect(box).toHaveProperty('value', '');
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('First line\nsecond line');
  });

  it('sends nothing for a blank question, and nothing new while an answer streams', async () => {
    const { actor, calls, ask, messages } = await openAsk();
    const box = screen.getByRole('textbox', { name: messages.ask.form.label });
    await actor.type(box, '   {Enter}');
    expect(calls.filter((c) => c.path === '/api/ask/stream')).toHaveLength(0);

    await actor.clear(box);
    await ask();
    await ask('A second question');
    expect(calls.filter((c) => c.path === '/api/ask/stream')).toHaveLength(1);
    expect(screen.getByRole('button', { name: messages.ask.form.submitting })).toHaveProperty(
      'disabled',
      true,
    );
  });
});

describe('never looks frozen', () => {
  it('says the stage in words at once, then each stage the server reports', async () => {
    const { ask, send } = await openAsk();
    await ask();
    expect(status().textContent).toContain(en.ask.stage.starting);

    await send('stage', { stage: 'searching' });
    expect(status().textContent).toContain(en.ask.stage.searching);

    await send('stage', { stage: 'reading', sources: 6, band: 'answer' });
    expect(status().textContent).toContain(en.ask.stage.reading);
    expect(status().textContent).toContain(fill(en.ask.detail.reading, { sources: '6' }));

    await send('stage', { stage: 'queued', position: 2 });
    expect(status().textContent).toContain(fill(en.ask.detail.queued, { position: '2' }));
  });

  it('shows no long-answer notice for an estimate of 20 seconds or less', async () => {
    const { ask, send } = await openAsk();
    await ask();
    await send('stage', { stage: 'reading', sources: 4, band: 'answer' });
    await send('eta', { expected_seconds: 20 });
    expect(
      screen.getByText(fill(en.ask.wait.elapsed, { elapsed: '0 seconds', expected: '20 seconds' })),
    ).toBeDefined();
    expect(screen.queryByText(/may take about/)).toBeNull();
  });

  it('above 20 seconds, gives the notice before writing starts', async () => {
    const { ask, send } = await openAsk();
    await ask();
    await send('stage', { stage: 'reading', sources: 4, band: 'answer' });
    await send('eta', { expected_seconds: 45 });
    expect(status().textContent).toContain(fill(en.ask.wait.notice, { duration: '45 seconds' }));
    expect(status().textContent).not.toContain(en.ask.stage.writing);

    await send('stage', { stage: 'writing' });
    await send('token', { text: 'In 2021' });
    expect(screen.queryByText(/may take about/)).toBeNull();
  });

  it('counts elapsed time against the estimate, then says it is taking longer', async () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] });
    const { ask, send } = await openAsk();
    await ask();
    await send('stage', { stage: 'reading', sources: 4, band: 'answer' });
    await send('eta', { expected_seconds: 24 });
    const elapsed = (seconds: number) =>
      fill(en.ask.wait.elapsed, { elapsed: `${String(seconds)} seconds`, expected: '24 seconds' });
    expect(screen.getByText(elapsed(0))).toBeDefined();

    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(screen.getByText(elapsed(10))).toBeDefined();

    // 1.25 × 24 = 30 seconds: still on time at 30, longer than usual after.
    act(() => {
      vi.advanceTimersByTime(20_000);
    });
    expect(screen.getByText(elapsed(30))).toBeDefined();
    act(() => {
      vi.advanceTimersByTime(1_000);
    });
    expect(screen.getByText(fill(en.ask.wait.overrun, { elapsed: '31 seconds' }))).toBeDefined();
    expect(screen.queryByText(elapsed(31))).toBeNull();

    // The first token ends the wait: the counter goes, the words keep coming.
    await send('token', { text: 'In 2021' });
    expect(screen.queryByText(/taking longer than usual/)).toBeNull();
    expect(status().textContent).toContain(en.ask.stage.writing);
    expect(screen.getByText('In 2021')).toBeDefined();
  });

  it('formats the counter in Arabic with Latin digits by default', async () => {
    const { ask, send } = await openAsk(AR_VIEWER);
    await ask('كم عدد الفتيات المسجلات في عام 2021؟');
    await send('eta', { expected_seconds: 45 });
    expect(status().textContent).toContain(fill(ar.ask.wait.notice, { duration: '45 ثانية' }));
  });
});

describe('validation wins over streaming', () => {
  it('shows the amber banner from the reading stage, before the first token', async () => {
    const { ask, send } = await openAsk();
    await ask();
    await send('stage', { stage: 'reading', sources: 3, band: 'low_confidence' });
    expect(screen.getByRole('note').textContent).toBe(en.answer.lowConfidence);
    expect(screen.queryByText(/In 2021/)).toBeNull();

    await send('token', { text: 'In 2021 the programme' });
    await send('final', FINAL_LOW_CONFIDENCE);
    expect(screen.getByRole('note').textContent).toBe(en.answer.lowConfidence);
    expect(screen.getByText(ANSWER_TEXT)).toBeDefined();
  });

  it('has no banner in the answer band', async () => {
    const { ask, send } = await openAsk();
    await ask();
    await send('stage', { stage: 'reading', sources: 3, band: 'answer' });
    await send('final', FINAL_ANSWERED);
    expect(screen.queryByRole('note')).toBeNull();
  });

  it('replaces the streamed text with the validated answer', async () => {
    const { ask, send } = await openAsk();
    await ask();
    await send('stage', { stage: 'writing' });
    await send('token', { text: 'A streamed draft ' });
    await send('token', { text: 'that will be replaced' });
    expect(screen.getByText('A streamed draft that will be replaced')).toBeDefined();

    await send('final', FINAL_ANSWERED);
    expect(screen.queryByText(/streamed draft/)).toBeNull();
    expect(screen.getByText(ANSWER_TEXT)).toBeDefined();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it.each([
    ['gate', FINAL_GATE, en.ask.refusal.gate],
    ['sentinel', FINAL_SENTINEL, en.ask.refusal.read],
    [
      'no_valid_citation',
      { ...FINAL_SENTINEL, refusal_reason: 'no_valid_citation' },
      en.ask.refusal.read,
    ],
  ] as const)('a %s refusal removes the streamed text and says why', async (_, final, reason) => {
    const { ask, send } = await openAsk();
    await ask();
    await send('token', { text: 'The enrolment figure was' });
    await send('final', final);

    expect(screen.queryByText(/enrolment figure/)).toBeNull();
    expect(screen.getByText(en.answer.refusal)).toBeDefined();
    expect(screen.getByText(reason)).toBeDefined();
    expect(screen.queryByRole('region', { name: en.ask.citations.heading })).toBeNull();
  });

  it('tells the two kinds of refusal apart in both languages', () => {
    expect(en.ask.refusal.gate).not.toBe(en.ask.refusal.read);
    expect(ar.ask.refusal.gate).not.toBe(ar.ask.refusal.read);
  });

  it('lists at most three documents to check under a refusal', async () => {
    const { ask, send } = await openAsk();
    await ask();
    await send('final', FINAL_GATE);
    const list = screen.getByRole('list', { name: en.ask.refusal.nearest });
    const links = within(list).getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual(NEAREST.slice(0, 3).map((d) => d.title));
    expect(links[0]?.getAttribute('href')).toBe(`/documents/${NEAREST[0]?.document_id ?? ''}`);
  });

  it('turns an error event into a translated message and offers to try again', async () => {
    const { ask, send, asks, calls, actor } = await openAsk();
    await ask();
    await send('token', { text: 'Half an answer' });
    await send('error', { error: { code: 'INTERNAL_ERROR', params: {} } });
    expect(screen.getByRole('alert').textContent).toBe(en.errors.INTERNAL_ERROR);
    expect(screen.queryByText('Half an answer')).toBeNull();

    await actor.click(screen.getByRole('button', { name: en.ask.retry }));
    expect(asks.all).toHaveLength(2);
    expect(calls.filter((c) => c.path === '/api/ask/stream').at(-1)?.body).toEqual({
      question: QUESTION,
    });
  });

  it('a stream that ends without a final answer is an error, not an answer', async () => {
    const { ask, send, asks } = await openAsk();
    await ask();
    await send('token', { text: 'Unvalidated words' });
    await act(async () => {
      asks.current.close();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(screen.getByRole('alert').textContent).toBe(en.errors.NETWORK_ERROR);
    expect(screen.queryByText('Unvalidated words')).toBeNull();
  });

  it('a 401 ends the session and goes to the login page', async () => {
    const { ask, router } = await openAsk(EN_VIEWER, {
      handlers: { 'POST /api/ask/stream': () => apiError(401, 'UNAUTHENTICATED') },
    });
    await ask();
    expect(await screen.findByRole('button', { name: en.auth.login.submit })).toBeDefined();
    expect(router.state.location.pathname).toBe('/login');
  });
});

describe('citations', () => {
  it('shows title, page and snippet, and opens the viewer at that page', async () => {
    const { ask, send, actor, router } = await openAsk();
    await ask();
    await send('final', FINAL_ANSWERED);

    const card = screen.getByRole('link', { name: new RegExp(PDF_CITATION.title) });
    expect(card.textContent).toContain(fill(en.ask.citations.page, { page: '7' }));
    expect(card.textContent).toContain(PDF_CITATION.snippet);
    expect(card.getAttribute('href')).toBe(`/documents/${PDF_CITATION.document_id}?page=7`);
    expect(card.querySelector('[dir="auto"]')?.textContent).toBe(PDF_CITATION.title);

    await actor.click(card);
    expect(router.state.location.pathname).toBe(`/documents/${PDF_CITATION.document_id}`);
    expect(router.state.location.search).toBe('?page=7');
  });

  it.each([
    ['en', EN_VIEWER, en],
    ['ar', AR_VIEWER, ar],
  ] as const)(
    'notes converted pages on Word and text sources only (%s)',
    async (_, user, messages) => {
      const { ask, send } = await openAsk(user);
      await ask();
      await send('final', {
        ...FINAL_ANSWERED,
        answer: `${ANSWER_TEXT} [3]`,
        citations: [PDF_CITATION, DOCX_CITATION, { ...TXT_CITATION, rank: 3 }],
      });
      const card = (title: string) =>
        screen.getByRole('link', { name: new RegExp(title.replace(/[()]/g, '.')) });
      expect(card(PDF_CITATION.title).textContent).not.toContain(
        messages.ask.citations.convertedWord,
      );
      expect(card(PDF_CITATION.title).textContent).not.toContain(
        messages.ask.citations.convertedOther,
      );
      expect(card(DOCX_CITATION.title).textContent).toContain(messages.ask.citations.convertedWord);
      expect(card(TXT_CITATION.title).textContent).toContain(messages.ask.citations.convertedOther);
    },
  );
});

describe('language switch', () => {
  it('keeps the shown answer and makes no GET', async () => {
    const { ask, send, actor, calls } = await openAsk();
    await ask();
    await send('stage', { stage: 'reading', sources: 2, band: 'low_confidence' });
    await send('final', FINAL_LOW_CONFIDENCE);
    const before = gets(calls).length;

    await actor.click(screen.getByRole('button', { name: en.language.switch }));

    expect(document.documentElement.dir).toBe('rtl');
    expect(screen.getByRole('heading', { level: 1, name: ar.pages.ask.title })).toBeDefined();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(QUESTION);
    expect(screen.getByText(ANSWER_TEXT)).toBeDefined();
    expect(screen.getByRole('note').textContent).toBe(ar.answer.lowConfidence);
    // The snippet's Latin code sits in its own <bdi>, so compare the card's whole text.
    expect(
      screen.getByRole('link', { name: new RegExp(DOCX_CITATION.title) }).textContent,
    ).toContain(DOCX_CITATION.snippet);
    expect(screen.getByText(ar.ask.citations.convertedWord)).toBeDefined();
    expect(gets(calls).length).toBe(before);
  });

  it('re-translates the stage of an answer still on its way', async () => {
    const { ask, send, actor } = await openAsk();
    await ask();
    await send('stage', { stage: 'searching' });
    await actor.click(screen.getByRole('button', { name: en.language.switch }));
    expect(status().textContent).toContain(ar.ask.stage.searching);
  });
});

describe('history panel', () => {
  const HISTORY = [
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
  const STORED = {
    ...FINAL_ANSWERED,
    id: QUERY_ID,
    question: HISTORY[0]?.question,
    created_at: HISTORY[0]?.created_at,
  };
  const handlers = {
    'GET /api/queries': () => json(200, HISTORY),
    [`GET /api/queries/${QUERY_ID}`]: () => json(200, STORED),
  };

  it('loads only when opened, then shows a stored answer with its citations', async () => {
    const { actor, calls } = await openAsk(EN_VIEWER, { handlers });
    expect(calls.some((c) => c.path.startsWith('/api/queries'))).toBe(false);

    await actor.click(screen.getByRole('button', { name: en.ask.history.toggle }));
    const panel = await screen.findByRole('complementary', { name: en.ask.history.heading });
    const item = await within(panel).findByRole('button', { name: new RegExp('2021') });
    expect(within(panel).getByText(en.ask.outcome.no_answer)).toBeDefined();

    await actor.click(item);
    expect(await screen.findByText(ANSWER_TEXT)).toBeDefined();
    expect(
      screen.getByRole('heading', { level: 2, name: HISTORY[0]?.question ?? '' }),
    ).toBeDefined();
    expect(screen.getByRole('link', { name: new RegExp(PDF_CITATION.title) })).toBeDefined();
    expect(gets(calls).map((c) => c.path)).toContain(`/api/queries/${QUERY_ID}`);
    expect(item.getAttribute('aria-current')).toBe('true');
    expect(within(panel).queryByText(en.ask.history.guestHint)).toBeNull();
  });

  it('says so when there is no history yet', async () => {
    const { actor } = await openAsk(EN_VIEWER, {
      handlers: { 'GET /api/queries': () => json(200, []) },
    });
    await actor.click(screen.getByRole('button', { name: en.ask.history.toggle }));
    expect(await screen.findByText(en.ask.history.empty)).toBeDefined();
  });

  it('is there for the guest too, with a this-session-only hint', async () => {
    // For the shared guest account the server lists only this session's questions (R1).
    const { ask, send, actor } = await openAsk(
      { ...GUEST, preferred_language: 'en' },
      { handlers: { 'GET /api/queries': () => json(200, []) } },
    );
    await ask();
    await send('final', FINAL_ANSWERED);
    expect(screen.getByText(ANSWER_TEXT)).toBeDefined();
    await actor.click(screen.getByRole('button', { name: en.ask.history.toggle }));
    expect(await screen.findByText(en.ask.history.empty)).toBeDefined();
    expect(screen.getByText(en.ask.history.guestHint)).toBeDefined();
  });

  it("never shows the previous session's cached history after a new guest login", async () => {
    const guest: Me = { ...GUEST, preferred_language: 'en' };
    let release: (response: Response) => void = () => undefined;
    let session = 1;
    const { actor, queryClient } = await openAsk(guest, {
      handlers: {
        // The first session has one question; the second session's list is held back, so
        // the test can look at the panel while it loads.
        'GET /api/queries': () =>
          session === 1
            ? json(200, [HISTORY[0]])
            : new Promise<Response>((resolve) => {
                release = resolve;
              }),
      },
    });
    const toggle = () => screen.getByRole('button', { name: en.ask.history.toggle });
    await actor.click(toggle());
    expect(await screen.findByText(HISTORY[0]?.question ?? '')).toBeDefined();

    // Sign-out, then a fresh guest login in the same page.
    session = 2;
    act(() => {
      queryClient.setQueryData(sessionQueryKey, null);
    });
    await screen.findByRole('button', { name: en.auth.login.guest });
    act(() => {
      queryClient.setQueryData(sessionQueryKey, guest);
    });
    await screen.findByRole('heading', { level: 1, name: en.pages.ask.title });

    await actor.click(toggle());
    expect(screen.getByText(en.common.loading)).toBeDefined();
    expect(screen.queryByText(HISTORY[0]?.question ?? '')).toBeNull();
    release(json(200, []));
    expect(await screen.findByText(en.ask.history.empty)).toBeDefined();
    expect(screen.queryByText(HISTORY[0]?.question ?? '')).toBeNull();
  });
});
