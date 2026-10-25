// pdf.js, self-hosted. Loaded with import() from the viewer only, so no other screen downloads
// it. Vite bundles the worker as a same-origin .js asset (the nginx CSP allows worker-src
// 'self'; nginx has no MIME type for .mjs, so the worker must not ship as one).
import { getDocument, GlobalWorkerOptions, type PDFDocumentLoadingTask } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?worker&url';

GlobalWorkerOptions.workerSrc = workerUrl;

/**
 * Open a PDF from its bytes. pdf.js takes ownership of `data` (it is transferred to the
 * worker), so pass a copy of anything that is kept elsewhere.
 */
export function openPdf(data: Uint8Array): PDFDocumentLoadingTask {
  return getDocument({
    data,
    // The CSP has no 'wasm-unsafe-eval': skip the WebAssembly decoders instead of tripping it.
    useWasm: false,
    enableXfa: false,
    // pdf.js draws each glyph from the embedded font itself. Handing the rebuilt fonts to the
    // browser instead dropped letters and commas from the seed corpus's Arabic pages (Amiri
    // subsets): "الإيرادات" came out as "الإيرا ا ت" and 2,780,000 as 2 780 000.
    disableFontFace: true,
  });
}
