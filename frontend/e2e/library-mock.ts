// F3/F4 test helpers: signed-in users, a small in-memory documents API that behaves like B3's
// (filters, visibility by role, lifecycle, upload, status steps), and a generated PDF.
// The e2e container mounts frontend/ only, so the seed PDFs can't be served; the generated
// PDF has real pages (shapes, no text) for pdf.js to draw. Data is synthetic: titles from the
// seed corpus, users obviously fake.
import type { Page, Request, Route } from '@playwright/test';

export type Role = 'viewer' | 'editor' | 'admin';

const USERS = {
  viewer: { id: '00000000-0000-4000-8000-000000000001', name: 'ليلى تجريبية' },
  editor: { id: '00000000-0000-4000-8000-000000000002', name: 'Sami Example' },
  admin: { id: '00000000-0000-4000-8000-000000000003', name: 'مدير تجريبي' },
} as const;

export function user(role: Role, language: 'ar' | 'en' = 'en') {
  return {
    ...USERS[role],
    email: `${role}@example.org`,
    role,
    preferred_language: language,
    is_guest: false,
  };
}

/** GET /api/me answers with the user; PATCH /api/me (the saved language) is accepted. */
export async function signInAs(page: Page, role: Role, language: 'ar' | 'en' = 'en') {
  await page.route('**/api/me', (route) =>
    route.request().method() === 'PATCH'
      ? route.fulfill({ status: 204 })
      : route.fulfill({ json: user(role, language) }),
  );
}

export const PROGRAMMES = [
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
  {
    id: 'a0000000-0000-4000-8000-00000000000c',
    code: 'YEP',
    name_ar: 'برنامج تمكين الشباب للتوظيف',
    name_en: 'Youth Employment Empowerment Programme',
  },
];

type Status = 'queued' | 'extracting' | 'indexing' | 'ready' | 'failed';

export interface MockDocument {
  id: string;
  title: string;
  original_filename: string;
  file_type: 'pdf' | 'docx' | 'txt';
  is_converted: boolean;
  category: string | null;
  year: number | null;
  programme_id: string | null;
  uploaded_by: { id: string; name: string };
  uploaded_at: string;
  page_count: number | null;
  status: Status;
  error_code: string | null;
  error_params: Record<string, unknown> | null;
  restricted: boolean;
  is_archived: boolean;
  is_seed: boolean;
}

let nextId = 1;
const newId = () => `d0000000-0000-4000-8000-${String(nextId++).padStart(12, '0')}`;

export function makeDoc(overrides: Partial<MockDocument> & { title: string }): MockDocument {
  const fileType = overrides.file_type ?? 'pdf';
  return {
    id: newId(),
    original_filename: `${overrides.title.toLowerCase().replace(/\W+/g, '-')}.${fileType}`,
    file_type: fileType,
    is_converted: fileType !== 'pdf',
    category: 'annual_report',
    year: 2021,
    programme_id: null,
    uploaded_by: USERS.editor,
    uploaded_at: '2026-10-20T09:30:00Z',
    page_count: 6,
    status: 'ready',
    error_code: null,
    error_params: null,
    restricted: false,
    is_archived: false,
    is_seed: true,
    ...overrides,
  };
}

/** A small Library: one of each case F3 must show. */
export function seedLibrary(): Record<string, MockDocument> {
  return {
    annual2021: makeDoc({ title: 'Annual Report 2021', year: 2021, page_count: 16 }),
    annual2016: makeDoc({ title: 'التقرير السنوي 2016', year: 2016, page_count: 6 }),
    budget2018: makeDoc({
      title: 'الموازنة التقديرية لعام 2018',
      file_type: 'docx',
      category: 'budget',
      year: 2018,
      page_count: 4,
    }),
    wlpAgreement: makeDoc({
      title: 'اتفاقية تمويل المشروع WLP-2022-01 مع مؤسسة بيارق النور الخيرية',
      category: 'donor_agreement',
      year: 2022,
      programme_id: PROGRAMMES[1]?.id ?? null,
      page_count: 5,
      restricted: true,
    }),
    gepSurvey: makeDoc({
      title: 'دراسة واقع التحاق الفتيات بالتعليم الأساسي في سهل القمر 2015',
      category: null,
      year: 2015,
      programme_id: PROGRAMMES[0]?.id ?? null,
      page_count: 4,
    }),
    scannedMinutes: makeDoc({
      title: 'محضر اجتماع مجلس الإدارة رقم 4/2017',
      original_filename: 'board-minutes-2017-scan.pdf',
      category: 'board_minutes',
      year: 2017,
      page_count: 3,
      status: 'failed',
      error_code: 'NO_TEXT_LAYER',
      error_params: { pages: 3, scanned_pages: 3 },
      is_seed: false,
    }),
    draftBudget: makeDoc({
      title: '2024 Budget, Draft for Discussion',
      category: 'budget',
      year: 2024,
      page_count: 5,
      is_archived: true,
    }),
  };
}

/** How an uploaded file fares: refused at upload, or the statuses it steps through. */
export type UploadOutcome =
  | { reject: { status: number; code: string; params?: Record<string, unknown> } }
  | { steps: Status[]; failure?: { code: string; params?: Record<string, unknown> } };

interface MockOptions {
  role: Role;
  documents: MockDocument[];
  /** Decides each upload by file name. Default: accepted, then queued → … → ready. */
  upload?: (filename: string) => UploadOutcome;
  /** Milliseconds each upload takes, so concurrency can be observed. */
  uploadDelayMs?: number;
}

export interface MockLibrary {
  documents: Map<string, MockDocument>;
  /** Every /api/documents request, in order. */
  requests: { method: string; url: URL; body: unknown }[];
  /** The most uploads in flight at the same time. */
  maxConcurrentUploads: () => number;
}

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, json: body });
}

function error(route: Route, status: number, code: string, params: Record<string, unknown> = {}) {
  return json(route, status, { error: { code, params } });
}

function uploadedName(request: Request): string {
  const body = request.postDataBuffer()?.toString('latin1') ?? '';
  const raw = /filename="([^"]*)"/.exec(body)?.[1] ?? 'upload.pdf';
  return Buffer.from(raw, 'latin1').toString('utf8');
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Serve /api/programmes and /api/documents* from memory, the way B3 does: the same filters,
 * restricted documents only for editors and admins, archived ones only on request (or by id).
 */
export async function mockLibrary(page: Page, options: MockOptions): Promise<MockLibrary> {
  const documents = new Map(options.documents.map((doc) => [doc.id, { ...doc }]));
  // Processing stages still ahead of each uploaded document; a failure is the last stage.
  type Step = Status | { code: string; params?: Record<string, unknown> };
  const steps = new Map<string, Step[]>();
  const requests: MockLibrary['requests'] = [];
  const canSeeRestricted = options.role !== 'viewer';
  let inFlight = 0;
  let maxInFlight = 0;

  const visible = (doc: MockDocument) => canSeeRestricted || !doc.restricted;

  /** Each poll that returns a processing document moves it one stage on. */
  const advance = (doc: MockDocument) => {
    const next = steps.get(doc.id)?.shift();
    if (next === undefined) return;
    if (typeof next === 'object') {
      Object.assign(doc, {
        status: 'failed',
        error_code: next.code,
        error_params: next.params ?? {},
      });
    } else {
      doc.status = next;
      if (next === 'ready') doc.page_count = 4;
    }
  };

  await page.route('**/api/programmes', (route) => json(route, 200, PROGRAMMES));
  await page.route(
    (url) => url.pathname.startsWith('/api/documents'),
    async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const method = request.method();
      let body: unknown = null;
      const contentType = request.headers()['content-type'] as string | undefined;
      if (method !== 'GET' && !contentType?.startsWith('multipart/')) {
        body = request.postDataJSON() as unknown;
      }
      requests.push({ method, url, body });
      if (method !== 'GET' && request.headers()['x-sanad'] !== '1') {
        return error(route, 403, 'CSRF_REJECTED');
      }

      const parts = url.pathname.split('/').filter(Boolean); // api, documents, id?, action?
      const id = parts[2];
      const action = parts[3];

      if (!id && method === 'GET') {
        const q = url.searchParams;
        const ids = q.getAll('ids');
        let items = [...documents.values()].filter(visible);
        if (ids.length) items = items.filter((doc) => ids.includes(doc.id));
        else if (q.get('include_archived') !== 'true') items = items.filter((d) => !d.is_archived);
        const term = q.get('q')?.toLowerCase();
        if (term) items = items.filter((doc) => doc.title.toLowerCase().includes(term));
        const types = q.getAll('file_type');
        if (types.length) items = items.filter((doc) => types.includes(doc.file_type));
        const categories = q.getAll('category');
        const uncategorised = q.get('uncategorised') === 'true';
        if (categories.length || uncategorised) {
          items = items.filter(
            (doc) =>
              (doc.category !== null && categories.includes(doc.category)) ||
              (uncategorised && doc.category === null),
          );
        }
        const from = Number(q.get('year_from') ?? 0);
        const to = Number(q.get('year_to') ?? 9999);
        if (q.has('year_from') || q.has('year_to')) {
          items = items.filter((doc) => doc.year !== null && doc.year >= from && doc.year <= to);
        }
        const programmes = q.getAll('programme_id');
        if (programmes.length) {
          items = items.filter((doc) => programmes.includes(doc.programme_id ?? ''));
        }
        const statuses = q.getAll('status');
        if (statuses.length) items = items.filter((doc) => statuses.includes(doc.status));
        if (q.has('restricted') && canSeeRestricted) {
          items = items.filter((doc) => doc.restricted === (q.get('restricted') === 'true'));
        }
        if (ids.length) items.forEach(advance);
        const pageNumber = Number(q.get('page') ?? 1);
        const pageSize = Number(q.get('page_size') ?? 25);
        return json(route, 200, {
          items: items.slice((pageNumber - 1) * pageSize, pageNumber * pageSize),
          total: items.length,
          page: pageNumber,
          page_size: pageSize,
        });
      }

      if (!id && method === 'POST') {
        inFlight += 1;
        maxInFlight = Math.max(maxInFlight, inFlight);
        await sleep(options.uploadDelayMs ?? 0);
        inFlight -= 1;
        const filename = uploadedName(request);
        const outcome = options.upload?.(filename) ?? {
          steps: ['extracting', 'indexing', 'ready'] as Status[],
        };
        if ('reject' in outcome) {
          return error(route, outcome.reject.status, outcome.reject.code, outcome.reject.params);
        }
        const doc = makeDoc({
          title: filename.replace(/\.\w+$/, ''),
          original_filename: filename,
          file_type: (/\.(docx|txt)$/.exec(filename)?.[1] ?? 'pdf') as MockDocument['file_type'],
          status: 'queued',
          page_count: null,
          is_seed: false,
        });
        documents.set(doc.id, doc);
        steps.set(
          doc.id,
          outcome.failure ? [...outcome.steps, outcome.failure] : [...outcome.steps],
        );
        return json(route, 201, doc);
      }

      const doc = id ? documents.get(id) : undefined;
      if (!doc || !visible(doc)) return error(route, 404, 'NOT_FOUND');

      if (method === 'GET' && !action) return json(route, 200, doc);
      if (method === 'GET' && action === 'file') {
        if (doc.status !== 'ready') return error(route, 409, 'DOCUMENT_NOT_READY');
        return route.fulfill({
          status: 200,
          contentType: 'application/pdf',
          body: buildPdf(doc.page_count ?? 1),
        });
      }
      if (method === 'PATCH') {
        Object.assign(doc, body);
        return json(route, 200, doc);
      }
      if (method === 'POST' && action === 'archive') {
        doc.is_archived = true;
        return json(route, 200, doc);
      }
      if (method === 'POST' && action === 'unarchive') {
        doc.is_archived = false;
        return json(route, 200, doc);
      }
      if (method === 'POST' && action === 'retry') {
        if (doc.status !== 'failed') return error(route, 409, 'DOCUMENT_NOT_RETRYABLE');
        Object.assign(doc, { status: 'queued', error_code: null, error_params: null });
        return json(route, 200, doc);
      }
      return error(route, 405, 'METHOD_NOT_ALLOWED');
    },
  );

  return { documents, requests, maxConcurrentUploads: () => maxInFlight };
}

/**
 * A valid PDF with `pageCount` A4 pages and no fonts: a grey band, then one dark square per
 * page number, so each page looks different. Byte offsets in the xref are computed, so pdf.js
 * opens it without repair.
 */
export function buildPdf(pageCount: number): Buffer {
  const objects: string[] = [];
  const pageIds: number[] = [];
  for (let i = 0; i < pageCount; i += 1) {
    const pageId = 3 + i * 2;
    const contentId = pageId + 1;
    pageIds.push(pageId);
    const squares = Array.from(
      { length: i + 1 },
      (_, k) => `${String(60 + (k % 20) * 24)} ${String(700 - Math.floor(k / 20) * 24)} 16 16 re f`,
    ).join('\n');
    const stream = `0.85 g 40 760 515 42 re f\n0.2 g\n${squares}\n0.6 g 40 80 515 560 re S`;
    objects[pageId] =
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents ${String(contentId)} 0 R /Resources << >> >>`;
    objects[contentId] = `<< /Length ${String(stream.length)} >>\nstream\n${stream}\nendstream`;
  }
  objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
  objects[2] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${String(id)} 0 R`).join(' ')}] /Count ${String(pageCount)} >>`;

  let out = '%PDF-1.4\n';
  const offsets: number[] = [];
  for (let id = 1; id < objects.length; id += 1) {
    offsets[id] = out.length;
    out += `${String(id)} 0 obj\n${objects[id] ?? ''}\nendobj\n`;
  }
  const xref = out.length;
  out += `xref\n0 ${String(objects.length)}\n0000000000 65535 f \n`;
  for (let id = 1; id < objects.length; id += 1) {
    out += `${String(offsets[id]).padStart(10, '0')} 00000 n \n`;
  }
  out += `trailer\n<< /Size ${String(objects.length)} /Root 1 0 R >>\nstartxref\n${String(xref)}\n%%EOF\n`;
  return Buffer.from(out, 'latin1');
}

/** Serve one document and its PDF (for specs that only open the viewer). */
export async function mockDocument(page: Page, doc: MockDocument) {
  await page.route('**/api/programmes', (route) => json(route, 200, PROGRAMMES));
  await page.route(`**/api/documents/${doc.id}`, (route) => json(route, 200, doc));
  await page.route(`**/api/documents/${doc.id}/file`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/pdf',
      body: buildPdf(doc.page_count ?? 1),
    }),
  );
}

/** Console errors, page errors and CSP violations; a viewer page must have none. */
export async function watchProblems(page: Page): Promise<() => Promise<string[]>> {
  const problems: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') problems.push(`console: ${msg.text()}`);
  });
  page.on('pageerror', (err) => problems.push(`pageerror: ${err.message}`));
  await page.addInitScript(() => {
    const store: string[] = [];
    (window as unknown as { __cspViolations: string[] }).__cspViolations = store;
    document.addEventListener('securitypolicyviolation', (event) => {
      store.push(`${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  return async () => {
    const csp = await page.evaluate(
      () => (window as unknown as { __cspViolations?: string[] }).__cspViolations ?? [],
    );
    return [...problems, ...csp.map((v) => `csp: ${v}`)];
  };
}
