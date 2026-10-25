// Documents contract (SYSTEM_DESIGN §4, §7; B3's `sanad/api/documents.py`). Hand-written until
// B3's OpenAPI types are generated (make gen-api-types), like the auth and Ask shapes.

export const FILE_TYPES = ['pdf', 'docx', 'txt'] as const;
export type FileType = (typeof FILE_TYPES)[number];

/** The client's six categories (Q5). There is no "other": null means uncategorised. */
export const CATEGORIES = [
  'annual_report',
  'donor_agreement',
  'programme_evaluation',
  'field_survey',
  'budget',
  'board_minutes',
] as const;
export type Category = (typeof CATEGORIES)[number];

/** SYSTEM_DESIGN §5.1. `ready` and `failed` are terminal. */
export const STATUSES = ['queued', 'extracting', 'indexing', 'ready', 'failed'] as const;
export type DocStatus = (typeof STATUSES)[number];

export function isTerminal(status: DocStatus): boolean {
  return status === 'ready' || status === 'failed';
}

export interface Uploader {
  id: string;
  name: string;
}

/** One item of GET /api/documents, and the body of GET/PATCH /api/documents/{id}. */
export interface DocumentItem {
  id: string;
  title: string;
  original_filename: string;
  file_type: FileType;
  /** DOCX and TXT are shown as a PDF rendition whose page numbers may differ from Word's. */
  is_converted: boolean;
  category: Category | null;
  year: number | null;
  programme_id: string | null;
  uploaded_by: Uploader;
  uploaded_at: string;
  page_count: number | null;
  status: DocStatus;
  error_code: string | null;
  error_params: Record<string, unknown> | null;
  restricted: boolean;
  is_archived: boolean;
}

export interface DocumentList {
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
}

/** GET /api/programmes (B2). */
export interface Programme {
  id: string;
  code: string;
  name_ar: string;
  name_en: string;
}

/** The Library's filters. Each one is a single choice in the UI. */
export interface LibraryFilters {
  q: string;
  fileType: FileType | null;
  /** A category, or 'none' for uncategorised documents only. */
  category: Category | 'none' | null;
  yearFrom: number | null;
  yearTo: number | null;
  programmeId: string | null;
  status: DocStatus | null;
  /** Editors and admins only: restricted documents, or the others. */
  access: 'restricted' | 'open' | null;
  includeArchived: boolean;
  page: number;
}

/** PATCH /api/documents/{id}: only the fields sent change; null clears a field. */
export interface DocumentPatch {
  title?: string;
  category?: Category | null;
  year?: number | null;
  programme_id?: string | null;
  restricted?: boolean;
}

/** The optional fields of POST /api/documents (multipart, one file per request). */
export interface UploadDetails {
  category: Category | null;
  year: number | null;
  programmeId: string | null;
  restricted: boolean;
}
