import { keepPreviousData, queryOptions } from '@tanstack/react-query';

import { apiFetch } from '../../lib/api';
import type { DocumentItem, DocumentList, DocumentPatch, LibraryFilters, Programme } from './types';
import { isTerminal } from './types';

export const PAGE_SIZE = 25;
/** The most ids one status poll may ask for (B3's limit on `ids`). */
export const MAX_IDS_PER_REQUEST = 100;
/** How often the Library refreshes while a document on screen is still being processed. */
const LIBRARY_REFRESH_MS = 3000;

const path = (id: string) => `/documents/${encodeURIComponent(id)}`;

/** The viewer's route (F4): /documents/:id, optionally at ?page=N. */
export function viewerPath(id: string, page?: number): string {
  return page ? `${path(id)}?page=${String(page)}` : path(id);
}

/**
 * The query string for GET /api/documents. List filters are repeated keys on the server
 * (file_type=pdf&file_type=docx); the UI sends at most one value each, and never an empty one.
 */
export function listParams(filters: LibraryFilters, pageSize = PAGE_SIZE): URLSearchParams {
  const params = new URLSearchParams();
  const q = filters.q.trim();
  if (q) params.set('q', q);
  if (filters.fileType) params.append('file_type', filters.fileType);
  if (filters.category === 'none') params.set('uncategorised', 'true');
  else if (filters.category) params.append('category', filters.category);
  if (filters.yearFrom !== null) params.set('year_from', String(filters.yearFrom));
  if (filters.yearTo !== null) params.set('year_to', String(filters.yearTo));
  if (filters.programmeId) params.append('programme_id', filters.programmeId);
  if (filters.status) params.append('status', filters.status);
  if (filters.access) params.set('restricted', String(filters.access === 'restricted'));
  if (filters.includeArchived) params.set('include_archived', 'true');
  params.set('page', String(filters.page));
  params.set('page_size', String(pageSize));
  return params;
}

export const documentKeys = {
  all: ['documents'] as const,
  list: (params: string) => ['documents', 'list', params] as const,
  detail: (id: string) => ['documents', 'detail', id] as const,
  status: (ids: readonly string[]) => ['documents', 'status', ...ids] as const,
};

export function libraryQuery(filters: LibraryFilters) {
  const params = listParams(filters).toString();
  return queryOptions({
    queryKey: documentKeys.list(params),
    queryFn: ({ signal }) => apiFetch<DocumentList>(`/documents?${params}`, { signal }),
    // The previous page stays on screen while the next one loads, so the table never jumps.
    placeholderData: keepPreviousData,
    // Rows still being processed refresh by themselves; a settled list never polls.
    refetchInterval: (query) =>
      query.state.data?.items.some((item) => !isTerminal(item.status)) ? LIBRARY_REFRESH_MS : false,
  });
}

export function documentQuery(id: string) {
  return queryOptions({
    queryKey: documentKeys.detail(id),
    queryFn: ({ signal }) => apiFetch<DocumentItem>(path(id), { signal }),
  });
}

/** The current state of these documents (the upload screen's poll), 100 ids per request. */
export async function fetchDocumentsById(
  ids: readonly string[],
  signal?: AbortSignal,
): Promise<DocumentItem[]> {
  const batches: string[][] = [];
  for (let i = 0; i < ids.length; i += MAX_IDS_PER_REQUEST) {
    batches.push(ids.slice(i, i + MAX_IDS_PER_REQUEST));
  }
  const lists = await Promise.all(
    batches.map((batch) => {
      const params = new URLSearchParams();
      for (const id of batch) params.append('ids', id);
      params.set('page_size', String(MAX_IDS_PER_REQUEST));
      return apiFetch<DocumentList>(`/documents?${params.toString()}`, signal ? { signal } : {});
    }),
  );
  return lists.flatMap((list) => list.items);
}

// Programme names are bilingual, so the list never depends on the UI language and a language
// switch never refetches it. Programmes change rarely; once per page load is enough.
export const programmesQuery = queryOptions({
  queryKey: ['programmes'] as const,
  queryFn: ({ signal }) => apiFetch<Programme[]>('/programmes', { signal }),
  staleTime: Infinity,
});

export function updateDocument(id: string, patch: DocumentPatch): Promise<DocumentItem> {
  return apiFetch<DocumentItem>(path(id), { method: 'PATCH', body: patch });
}

export type LifecycleAction = 'archive' | 'unarchive' | 'retry';

export function runLifecycle(id: string, action: LifecycleAction): Promise<DocumentItem> {
  return apiFetch<DocumentItem>(`${path(id)}/${action}`, { method: 'POST' });
}
