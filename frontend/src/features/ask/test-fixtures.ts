// Synthetic Ask payloads for the vitest suites, in the SYSTEM_DESIGN §6 shapes. Titles come
// from the seed corpus; the figures are invented, like the corpus itself.
import type { AnswerResult, Citation } from './types';

export const QUERY_ID = '3f0b8c4e-1d2a-4e6f-9a7b-000000000101';

export const PDF_CITATION: Citation = {
  rank: 1,
  document_id: 'd1a2b3c4-0000-4000-8000-000000002021',
  title: 'Annual Report 2021',
  page_number: 7,
  snippet:
    "In 2021 the Girls' Basic Education Support Programme enrolled 1,240 girls in 18 schools.",
  file_type: 'pdf',
  is_converted: false,
};

export const DOCX_CITATION: Citation = {
  rank: 2,
  document_id: 'd1a2b3c4-0000-4000-8000-000000002018',
  title: 'الموازنة التقديرية لعام 2018',
  page_number: 3,
  snippet: 'خُصص مبلغ 85,000 دولار لبرنامج دعم التعليم الأساسي للفتيات GEP-2019-02.',
  file_type: 'docx',
  is_converted: true,
};

export const TXT_CITATION: Citation = {
  rank: 1,
  document_id: 'd1a2b3c4-0000-4000-8000-000000002024',
  title: 'مسح رضا المستفيدين من المشروع SPC-2023-01 لعام 2024',
  page_number: 2,
  snippet: 'أفاد 87% من المستفيدين بأنهم راضون عن الخدمات المقدمة.',
  file_type: 'txt',
  is_converted: true,
};

export const ANSWER_TEXT =
  'In 2021 the programme enrolled 1,240 girls [1]. The 2018 budget set aside USD 85,000 for it [2].';

export const FINAL_ANSWERED: AnswerResult = {
  query_id: QUERY_ID,
  outcome: 'answered',
  band: 'answer',
  refusal_reason: null,
  answer: ANSWER_TEXT,
  citations: [PDF_CITATION, DOCX_CITATION],
  nearest_documents: [],
};

export const FINAL_LOW_CONFIDENCE: AnswerResult = {
  ...FINAL_ANSWERED,
  outcome: 'low_confidence',
  band: 'low_confidence',
};

export const NEAREST = [
  { document_id: 'd1a2b3c4-0000-4000-8000-000000003001', title: 'Annual Report 2023' },
  { document_id: 'd1a2b3c4-0000-4000-8000-000000003002', title: 'التقرير السنوي 2022' },
  {
    document_id: 'd1a2b3c4-0000-4000-8000-000000003003',
    title: 'Household Health Survey, Palm Plains, 2021',
  },
  { document_id: 'd1a2b3c4-0000-4000-8000-000000003004', title: 'Annual Report 2016' },
];

export const FINAL_GATE: AnswerResult = {
  query_id: QUERY_ID,
  outcome: 'no_answer',
  band: 'refuse',
  refusal_reason: 'gate',
  answer: null,
  citations: [],
  nearest_documents: NEAREST,
};

export const FINAL_SENTINEL: AnswerResult = {
  ...FINAL_GATE,
  band: 'answer',
  refusal_reason: 'sentinel',
  nearest_documents: [],
};

/** One SSE message as the server frames it. */
export function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/** A text/event-stream response whose events the test sends one at a time. */
export function fakeStream() {
  const encoder = new TextEncoder();
  let controller: ReadableStreamDefaultController<Uint8Array> | undefined;
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
  });
  const enqueue = (text: string) => controller?.enqueue(encoder.encode(text));
  return {
    response: () =>
      new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }),
    send: (event: string, data: unknown) => {
      enqueue(sse(event, data));
    },
    raw: enqueue,
    close: () => controller?.close(),
  };
}
