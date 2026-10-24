import type { PDFDocumentLoadingTask, PDFPageProxy } from 'pdfjs-dist';
import { useEffect, useState } from 'react';

export type PdfState =
  { status: 'loading' } | { status: 'ready'; pages: PDFPageProxy[] } | { status: 'error' };

/**
 * Open the PDF in pdf.js and load every page's size up front, so each page's placeholder has
 * its real shape and scrolling to page N lands on page N. Pages are drawn lazily (PdfPage).
 * Mount one per document (key it by id): the state starts at `loading`.
 */
export function usePdfDocument(bytes: ArrayBuffer | undefined): PdfState {
  const [state, setState] = useState<PdfState>({ status: 'loading' });

  useEffect(() => {
    if (!bytes) return;
    let cancelled = false;
    // A function, so TypeScript doesn't narrow the flag across the awaits below.
    const live = () => !cancelled;
    let task: PDFDocumentLoadingTask | null = null;
    import('./pdf')
      .then(async ({ openPdf }) => {
        if (!live()) return;
        // pdf.js detaches the buffer it is given; the cached copy stays intact.
        task = openPdf(new Uint8Array(bytes.slice(0)));
        const pdf = await task.promise;
        const pages = await Promise.all(
          Array.from({ length: pdf.numPages }, (_, i) => pdf.getPage(i + 1)),
        );
        if (live()) setState({ status: 'ready', pages });
      })
      .catch(() => {
        if (live()) setState({ status: 'error' });
      });
    return () => {
      cancelled = true;
      void task?.destroy();
    };
  }, [bytes]);

  return state;
}
