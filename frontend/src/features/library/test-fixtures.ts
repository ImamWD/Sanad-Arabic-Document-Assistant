// Synthetic Library data for unit tests: titles and programmes from the seed corpus, users
// obviously fake (CLAUDE.md rule 10).
import type { DocumentItem, DocumentList, Programme } from './types';

export const PROGRAMMES: Programme[] = [
  {
    id: 'a0000000-0000-4000-8000-00000000000a',
    code: 'GEP',
    name_ar: 'برنامج دعم التعليم الأساسي للفتيات',
    name_en: "Girls' Basic Education Support Programme",
  },
  {
    id: 'a0000000-0000-4000-8000-00000000000b',
    code: 'WLP',
    name_ar: 'برنامج سُبل العيش للنساء المعيلات',
    name_en: 'Livelihoods Programme for Women Heads of Household',
  },
];

const EDITOR = { id: '00000000-0000-4000-8000-000000000002', name: 'Sami Example' };

export function makeDocument(overrides: Partial<DocumentItem> = {}): DocumentItem {
  return {
    id: 'd0000000-0000-4000-8000-000000002021',
    title: 'Annual Report 2021',
    original_filename: 'annual-report-2021.pdf',
    file_type: 'pdf',
    is_converted: false,
    category: 'annual_report',
    year: 2021,
    programme_id: null,
    uploaded_by: EDITOR,
    uploaded_at: '2026-10-20T09:30:00Z',
    page_count: 16,
    status: 'ready',
    error_code: null,
    error_params: null,
    restricted: false,
    is_archived: false,
    ...overrides,
  };
}

export const ANNUAL_REPORT = makeDocument();

export const RESTRICTED_AGREEMENT = makeDocument({
  id: 'd0000000-0000-4000-8000-000000002022',
  title: 'اتفاقية تمويل المشروع WLP-2022-01 مع مؤسسة بيارق النور الخيرية',
  original_filename: 'wlp-donor-agreement-2022.pdf',
  category: 'donor_agreement',
  year: 2022,
  programme_id: 'a0000000-0000-4000-8000-00000000000b',
  page_count: 5,
  restricted: true,
});

export const UNCATEGORISED_SURVEY = makeDocument({
  id: 'd0000000-0000-4000-8000-000000002015',
  title: 'دراسة واقع التحاق الفتيات بالتعليم الأساسي في سهل القمر 2015',
  original_filename: 'gep-enrolment-survey-2015.pdf',
  category: null,
  year: 2015,
  programme_id: 'a0000000-0000-4000-8000-00000000000a',
  page_count: 4,
});

export const SCANNED_MINUTES = makeDocument({
  id: 'd0000000-0000-4000-8000-000000002017',
  title: 'محضر اجتماع مجلس الإدارة رقم 4/2017',
  original_filename: 'board-minutes-2017-scan.pdf',
  category: 'board_minutes',
  year: 2017,
  page_count: 3,
  status: 'failed',
  error_code: 'NO_TEXT_LAYER',
  error_params: { pages: 3, scanned_pages: 3 },
});

export const BUDGET_DOCX = makeDocument({
  id: 'd0000000-0000-4000-8000-000000002018',
  title: 'الموازنة التقديرية لعام 2018',
  original_filename: 'budget-2018.docx',
  file_type: 'docx',
  is_converted: true,
  category: 'budget',
  year: 2018,
  page_count: 4,
});

export function listOf(items: DocumentItem[], page = 1, pageSize = 25): DocumentList {
  return { items, total: items.length, page, page_size: pageSize };
}
