import { describe, expect, it } from 'vitest';

import { errorFromResponse } from '../library/api';
import { uploadForm } from './uploadFile';

const file = new File(['%PDF-1.7'], 'annual-report-2021.pdf', { type: 'application/pdf' });

describe('uploadForm', () => {
  it('leaves out empty optional fields (an empty year is a 422)', () => {
    const form = uploadForm(file, {
      category: null,
      year: null,
      programmeId: null,
      restricted: false,
    });
    expect([...form.keys()]).toEqual(['file', 'restricted']);
    expect(form.get('restricted')).toBe('false');
    expect((form.get('file') as File).name).toBe('annual-report-2021.pdf');
  });

  it('sends the batch details that are set', () => {
    const form = uploadForm(file, {
      category: 'annual_report',
      year: 2021,
      programmeId: 'a0000000-0000-4000-8000-00000000000a',
      restricted: true,
    });
    expect(Object.fromEntries([...form.entries()].filter(([key]) => key !== 'file'))).toEqual({
      category: 'annual_report',
      year: '2021',
      programme_id: 'a0000000-0000-4000-8000-00000000000a',
      restricted: 'true',
    });
  });
});

describe('errorFromResponse', () => {
  it('reads the code and params of the error envelope', () => {
    const error = errorFromResponse(
      409,
      JSON.stringify({ error: { code: 'DUPLICATE_DOCUMENT', params: { document_id: 'd-1' } } }),
    );
    expect([error.status, error.code, error.params]).toEqual([
      409,
      'DUPLICATE_DOCUMENT',
      { document_id: 'd-1' },
    ]);
  });

  it('never passes on prose or a page that is not the envelope', () => {
    expect(errorFromResponse(413, '<html>Request Entity Too Large</html>').code).toBe(
      'UNKNOWN_ERROR',
    );
    expect(errorFromResponse(500, JSON.stringify({ error: { code: 'not a code' } })).code).toBe(
      'UNKNOWN_ERROR',
    );
  });
});
