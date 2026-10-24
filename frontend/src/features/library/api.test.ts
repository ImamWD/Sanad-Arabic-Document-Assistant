import { describe, expect, it } from 'vitest';

import { listParams, viewerPath } from './api';
import { draftOf, patchFrom } from './editPatch';
import { filtersFromParams, filtersToParams, hasActiveFilters, parseYear } from './filters';
import { ANNUAL_REPORT, RESTRICTED_AGREEMENT } from './test-fixtures';
import type { LibraryFilters } from './types';

const NONE: LibraryFilters = filtersFromParams(new URLSearchParams());

describe('listParams', () => {
  it('sends only the page and page size when nothing is filtered', () => {
    expect(listParams(NONE).toString()).toBe('page=1&page_size=25');
  });

  it('maps every filter to the server parameter, with no empty values', () => {
    const params = listParams({
      q: '  التعليم  ',
      fileType: 'docx',
      category: 'donor_agreement',
      yearFrom: 2018,
      yearTo: 2022,
      programmeId: 'a0000000-0000-4000-8000-00000000000a',
      status: 'failed',
      access: 'restricted',
      includeArchived: true,
      page: 2,
    });
    expect(Object.fromEntries(params)).toEqual({
      q: 'التعليم',
      file_type: 'docx',
      category: 'donor_agreement',
      year_from: '2018',
      year_to: '2022',
      programme_id: 'a0000000-0000-4000-8000-00000000000a',
      status: 'failed',
      restricted: 'true',
      include_archived: 'true',
      page: '2',
      page_size: '25',
    });
  });

  it('asks for uncategorised documents with the uncategorised flag, not a category', () => {
    const params = listParams({ ...NONE, category: 'none', access: 'open' });
    expect(params.get('uncategorised')).toBe('true');
    expect(params.has('category')).toBe(false);
    expect(params.get('restricted')).toBe('false');
  });
});

describe('Library filters in the URL', () => {
  it('round-trips through the query string', () => {
    const filters: LibraryFilters = {
      ...NONE,
      q: 'Annual',
      fileType: 'pdf',
      category: 'none',
      yearFrom: 2016,
      includeArchived: true,
      page: 3,
    };
    const params = filtersToParams(filters);
    expect(params.toString()).toBe('q=Annual&type=pdf&category=none&from=2016&archived=1&page=3');
    expect(filtersFromParams(params)).toEqual(filters);
  });

  it('ignores values it does not know', () => {
    const filters = filtersFromParams(
      new URLSearchParams('type=exe&category=other&from=20&status=done&access=x&page=-2'),
    );
    expect(filters).toEqual(NONE);
    expect(hasActiveFilters(filters)).toBe(false);
  });

  it('accepts only four-digit years from 1900 to 2100', () => {
    expect(parseYear('2021')).toBe(2021);
    expect(parseYear('202')).toBeNull();
    expect(parseYear('1899')).toBeNull();
    expect(parseYear('2101')).toBeNull();
    expect(parseYear(null)).toBeNull();
  });
});

describe('the edit dialog patch', () => {
  it('sends nothing when nothing changed', () => {
    expect(patchFrom(RESTRICTED_AGREEMENT, draftOf(RESTRICTED_AGREEMENT))).toEqual({});
  });

  it('sends only the changed fields, and null for an emptied one', () => {
    const draft = {
      ...draftOf(RESTRICTED_AGREEMENT),
      title: ' New title ',
      year: '',
      programmeId: '',
    };
    expect(patchFrom(RESTRICTED_AGREEMENT, draft)).toEqual({
      title: 'New title',
      year: null,
      programme_id: null,
    });
  });

  it('clears the category to flag a document for review', () => {
    expect(patchFrom(ANNUAL_REPORT, { ...draftOf(ANNUAL_REPORT), category: '' })).toEqual({
      category: null,
    });
  });
});

it('builds the viewer path, with the page when there is one', () => {
  expect(viewerPath('doc 7')).toBe('/documents/doc%207');
  expect(viewerPath('doc-7', 3)).toBe('/documents/doc-7?page=3');
});
