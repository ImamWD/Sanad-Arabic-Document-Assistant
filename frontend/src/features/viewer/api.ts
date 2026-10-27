import { queryOptions } from '@tanstack/react-query';

import { ApiError, errorFromResponse, NETWORK_ERROR } from '../../lib/api';
import { documentKeys } from '../library/api';

/**
 * GET /api/documents/{id}/file: the PDF the viewer shows (for DOCX and TXT, the converted
 * rendition, whose pages are the ones citations count). Fetched here rather than by pdf.js so
 * a 404 or 409 DOCUMENT_NOT_READY arrives as a translated error code.
 */
export async function fetchPdf(id: string, signal: AbortSignal): Promise<ArrayBuffer> {
  let response: Response;
  try {
    response = await fetch(`/api/documents/${encodeURIComponent(id)}/file`, {
      headers: { Accept: 'application/pdf' },
      credentials: 'same-origin',
      signal,
    });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new ApiError(0, NETWORK_ERROR);
  }
  if (!response.ok) throw errorFromResponse(response.status, await response.text().catch(() => ''));
  return response.arrayBuffer();
}

export function pdfFileQuery(id: string) {
  return queryOptions({
    queryKey: [...documentKeys.all, 'file', id] as const,
    queryFn: ({ signal }) => fetchPdf(id, signal),
    // A document's PDF never changes, and it can be large: fetch it once per visit to the
    // viewer and drop it as soon as the viewer closes.
    staleTime: Infinity,
    gcTime: 0,
  });
}
