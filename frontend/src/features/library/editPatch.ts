import { parseYear } from './filters';
import type { Category, DocumentItem, DocumentPatch } from './types';

export interface EditDraft {
  title: string;
  category: string;
  year: string;
  programmeId: string;
}

export function draftOf(document: DocumentItem): EditDraft {
  return {
    title: document.title,
    category: document.category ?? '',
    year: document.year === null ? '' : String(document.year),
    programmeId: document.programme_id ?? '',
  };
}

/** The fields that changed; an emptied category, year or programme is sent as null. */
export function patchFrom(document: DocumentItem, draft: EditDraft): DocumentPatch {
  const patch: DocumentPatch = {};
  const title = draft.title.trim();
  if (title !== document.title) patch.title = title;
  const category = (draft.category || null) as Category | null;
  if (category !== document.category) patch.category = category;
  const year = draft.year.trim() === '' ? null : parseYear(draft.year);
  if (year !== document.year) patch.year = year;
  const programmeId = draft.programmeId || null;
  if (programmeId !== document.programme_id) patch.programme_id = programmeId;
  return patch;
}
