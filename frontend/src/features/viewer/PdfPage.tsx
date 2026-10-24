import type { PDFPageProxy } from 'pdfjs-dist';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { cx } from '../../lib/cx';
import { useFormat } from '../../lib/useFormat';
import styles from './PdfViewer.module.css';

interface PdfPageProps {
  page: PDFPageProxy;
  number: number;
  cited: boolean;
  /** Near the viewport: draw it. Far away: release the canvas (long documents stay light). */
  near: boolean;
  /** The pages column's width in CSS pixels; a change redraws at the new size. */
  width: number;
  register: (number: number, element: HTMLElement | null) => void;
}

/**
 * One page: a placeholder with the page's own shape, drawn on a canvas when near the
 * viewport. The canvas is never mirrored: only the viewer's chrome follows the UI direction.
 */
export function PdfPage({ page, number, cited, near, width, register }: PdfPageProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const size = useMemo(() => page.getViewport({ scale: 1 }), [page]);
  const [drawnAt, setDrawnAt] = useState<number | null>(null);
  const label = t('viewer.page', { page: format.number(number) });

  useEffect(() => {
    const canvas = canvasRef.current;
    const sheet = sheetRef.current;
    if (!near || !canvas || !sheet || width <= 0) return;
    const scale = (sheet.clientWidth / size.width) * (window.devicePixelRatio || 1);
    const viewport = page.getViewport({ scale });
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    const task = page.render({ canvas, viewport });
    let live = true;
    task.promise.then(
      () => {
        if (live) setDrawnAt(width);
      },
      () => undefined, // cancelled by the cleanup below, or a page pdf.js can't draw
    );
    return () => {
      live = false;
      task.cancel();
      canvas.width = 0;
      canvas.height = 0;
    };
  }, [near, page, size, width]);

  return (
    <div
      ref={(element) => {
        register(number, element);
      }}
      className={cx(styles.page, cited && styles.cited)}
      role="group"
      aria-label={label}
      aria-current={cited ? 'true' : undefined}
      data-page-number={number}
      data-cited={cited ? 'true' : undefined}
      data-rendered={near && drawnAt === width ? 'true' : undefined}
    >
      <div className={styles.pageHead} aria-hidden="true">
        <span>{label}</span>
        {cited && <span className={styles.citedBadge}>{t('viewer.citedPage')}</span>}
      </div>
      {cited && <span className={styles.srOnly}>{t('viewer.citedPage')}</span>}
      <div
        ref={sheetRef}
        className={styles.sheet}
        style={{ aspectRatio: `${String(size.width)} / ${String(size.height)}` }}
      >
        <canvas ref={canvasRef} className={styles.canvas} />
      </div>
    </div>
  );
}
