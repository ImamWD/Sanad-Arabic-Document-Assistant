// The Ask contract (SYSTEM_DESIGN §6, §7). R1 serves it; until then the tests fake it. Once
// R1's routes are in openapi.json, these can be checked against the generated schema.d.ts.

export type Outcome = 'answered' | 'low_confidence' | 'no_answer';
export type Band = 'answer' | 'low_confidence' | 'refuse';
export type RefusalReason = 'gate' | 'sentinel' | 'no_valid_citation';

export interface Citation {
  /** The [n] marker in the answer. */
  rank: number;
  document_id: string;
  title: string;
  /** A page of the viewer PDF (for DOCX and TXT, the converted rendition). */
  page_number: number;
  snippet: string;
  file_type: string;
  is_converted: boolean;
}

export interface NearestDocument {
  document_id: string;
  title: string;
}

/** A validated answer: the `final` stream event, or a stored query from the history. */
export interface AnswerResult {
  query_id: string;
  outcome: Outcome;
  band: Band | null;
  refusal_reason: RefusalReason | null;
  /** Null when the outcome is no_answer: streamed text is never kept as the answer. */
  answer: string | null;
  citations: Citation[];
  nearest_documents: NearestDocument[];
}

/** The stream events the UI acts on. An `error` event is thrown as an ApiError instead. */
export type StreamEvent =
  | { type: 'stage'; stage: 'queued'; position: number }
  | { type: 'stage'; stage: 'searching' }
  | { type: 'stage'; stage: 'reading'; sources: number; band: Band | null }
  | { type: 'stage'; stage: 'writing' }
  | { type: 'eta'; expectedSeconds: number }
  | { type: 'token'; text: string }
  | { type: 'final'; result: AnswerResult };

/** One row of GET /api/queries: the signed-in user's own questions, newest first. */
export interface QuerySummary {
  id: string;
  question: string;
  outcome: Outcome;
  created_at: string;
}

/** GET /api/queries/{id}: the question with its stored answer. */
export interface StoredQuery {
  question: string;
  created_at: string;
  result: AnswerResult;
}
