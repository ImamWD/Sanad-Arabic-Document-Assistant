// POST /api/documents with upload progress. fetch() can't report upload progress, so this one
// request uses XMLHttpRequest, with the same CSRF header, cookie and error envelope as apiFetch.
import {
  ApiError,
  errorFromResponse,
  NETWORK_ERROR,
  parseJson,
  UNKNOWN_ERROR,
} from '../../lib/api';
import type { DocumentItem, UploadDetails } from '../library/types';

/** The multipart body. Optional fields are left out when empty: an empty year is a 422. */
export function uploadForm(file: File, details: UploadDetails): FormData {
  const form = new FormData();
  form.append('file', file, file.name);
  if (details.category) form.append('category', details.category);
  if (details.year !== null) form.append('year', String(details.year));
  if (details.programmeId) form.append('programme_id', details.programmeId);
  form.append('restricted', String(details.restricted));
  return form;
}

export interface UploadOptions {
  /** Called with the share of bytes sent, 0 to 1. */
  onProgress?: (fraction: number) => void;
  signal?: AbortSignal;
}

/** Upload one file. Resolves with the new document (status `queued`). */
export function uploadFile(
  file: File,
  details: UploadDetails,
  { onProgress, signal }: UploadOptions = {},
): Promise<DocumentItem> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/documents');
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.setRequestHeader('X-Sanad', '1');
    // No Content-Type: the browser sets multipart/form-data with its boundary.

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onProgress?.(event.loaded / event.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const body = parseJson(xhr.responseText);
        if (
          typeof body === 'object' &&
          body !== null &&
          'id' in body &&
          typeof body.id === 'string'
        ) {
          onProgress?.(1);
          resolve(body as unknown as DocumentItem);
        } else {
          reject(new ApiError(xhr.status, UNKNOWN_ERROR));
        }
      } else {
        const error = errorFromResponse(xhr.status, xhr.responseText);
        // nginx refuses an oversized body itself, with an HTML page rather than the envelope.
        reject(
          xhr.status === 413 && error.code === UNKNOWN_ERROR
            ? new ApiError(413, 'FILE_TOO_LARGE')
            : error,
        );
      }
    };
    xhr.onerror = () => {
      reject(new ApiError(0, NETWORK_ERROR));
    };
    xhr.onabort = () => {
      reject(new DOMException('Upload aborted', 'AbortError'));
    };
    signal?.addEventListener('abort', () => {
      xhr.abort();
    });
    xhr.send(uploadForm(file, details));
  });
}
