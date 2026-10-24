// Ask screen settings (SYSTEM_DESIGN §6, §10).

declare global {
  interface ImportMetaEnv {
    /** ETA_NOTICE_SECONDS for the web bundle (default 20). */
    readonly VITE_ETA_NOTICE_SECONDS?: string;
  }
}

export const DEFAULT_ETA_NOTICE_SECONDS = 20;

export function parseNoticeSeconds(value: unknown): number {
  const seconds = typeof value === 'string' && value.trim() ? Number(value) : NaN;
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : DEFAULT_ETA_NOTICE_SECONDS;
}

/** Above this estimate, say "this answer may take about S seconds" before the wait. */
export const ETA_NOTICE_SECONDS = parseNoticeSeconds(import.meta.env.VITE_ETA_NOTICE_SECONDS);

/** Past this multiple of the estimate, say it is taking longer than usual. */
export const OVERRUN_FACTOR = 1.25;

/** A refusal lists at most this many "you may want to check" documents (D4). */
export const MAX_NEAREST_DOCUMENTS = 3;
