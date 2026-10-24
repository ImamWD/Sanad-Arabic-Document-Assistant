import type { PDFPageProxy } from 'pdfjs-dist';
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Icon } from '../../lib/Icon';
import { useFormat } from '../../lib/useFormat';
import { PdfPage } from './PdfPage';
import styles from './PdfViewer.module.css';

/** Pages within this distance of the viewport are drawn; the rest release their canvas. */
const NEAR_MARGIN = '150% 0px';
/** The page that crosses this line (a share of the viewport height) is the current page. */
const CURRENT_LINE = 0.35;

interface PdfViewerProps {
  pages: PDFPageProxy[];
  /** The page a citation pointed at (?page=N): opened, scrolled to and marked. */
  citedPage: number | null;
}

function clamp(page: number, count: number): number {
  return Math.min(Math.max(1, Math.round(page)), count);
}

/** Where a page's top lands when scrolled to: its scroll margin, below the sticky toolbar. */
function startLine(element: HTMLElement): number {
  return parseFloat(getComputedStyle(element).scrollMarginBlockStart) || 0;
}

/** The reader's place: a page, and how far down it the start line falls (0 to 1). */
interface Anchor {
  page: number;
  ratio: number;
}

/** The pages, top to bottom, with a toolbar for moving between them. */
export function PdfViewer({ pages, citedPage }: PdfViewerProps) {
  const { t, i18n } = useTranslation();
  const format = useFormat();
  const count = pages.length;
  const cited = citedPage !== null && citedPage <= count ? citedPage : null;
  const elements = useRef(new Map<number, HTMLElement>());
  const column = useRef<HTMLDivElement>(null);
  const [near, setNear] = useState<ReadonlySet<number>>(() => new Set());
  const [current, setCurrent] = useState(cited ?? 1);
  const [width, setWidth] = useState(0);
  const [draft, setDraft] = useState<string | null>(null);
  const inputId = useId();
  // Null until the reader is among the pages (above them, a layout change moves nothing).
  const anchor = useRef<Anchor | null>(cited === null ? null : { page: cited, ratio: 0 });

  /** Note which page is at the start line, and how far into it. */
  const measureAnchor = useCallback(() => {
    const first = elements.current.get(1);
    if (!first) return;
    const line = startLine(first);
    if (first.getBoundingClientRect().top > line) {
      anchor.current = null;
      return;
    }
    for (let number = 1; number <= count; number += 1) {
      const rect = elements.current.get(number)?.getBoundingClientRect();
      if (rect && rect.bottom > line) {
        const ratio = rect.height > 0 ? (line - rect.top) / rect.height : 0;
        anchor.current = { page: number, ratio: Math.min(Math.max(ratio, 0), 1) };
        return;
      }
    }
  }, [count]);

  /**
   * Put the reader back on the same spot of the same page after the layout moved under them:
   * a language switch reflows the header above the pages, and a resize changes page heights.
   */
  const restoreAnchor = useCallback(() => {
    const place = anchor.current;
    const element = place && elements.current.get(place.page);
    if (!place || !element) return;
    const rect = element.getBoundingClientRect();
    window.scrollBy({ top: rect.top + place.ratio * rect.height - startLine(element) });
  }, []);

  const register = useCallback((number: number, element: HTMLElement | null) => {
    if (element) elements.current.set(number, element);
    else elements.current.delete(number);
  }, []);

  const goTo = useCallback(
    (page: number) => {
      const target = clamp(page, count);
      elements.current.get(target)?.scrollIntoView({ block: 'start' });
      anchor.current = { page: target, ratio: 0 };
      setCurrent(target);
    },
    [count],
  );

  // Open at the cited page (and again whenever ?page= changes while the viewer is open).
  useEffect(() => {
    if (cited === null) return;
    const frame = requestAnimationFrame(() => {
      goTo(cited);
    });
    return () => {
      cancelAnimationFrame(frame);
    };
  }, [cited, goTo]);

  // Draw the pages near the viewport only.
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        setNear((previous) => {
          const next = new Set(previous);
          for (const entry of entries) {
            const number = Number((entry.target as HTMLElement).dataset.pageNumber);
            if (entry.isIntersecting) next.add(number);
            else next.delete(number);
          }
          return next;
        });
      },
      { rootMargin: NEAR_MARGIN },
    );
    for (const element of elements.current.values()) observer.observe(element);
    return () => {
      observer.disconnect();
    };
  }, [pages]);

  // Redraw at the new size when the column's width changes (window resize, sidebar), and
  // keep the reader's place, since every page's height changed with it.
  useEffect(() => {
    const element = column.current;
    if (!element) return;
    let last = 0;
    const observer = new ResizeObserver(([entry]) => {
      if (!entry) return;
      const next = Math.round(entry.contentRect.width);
      if (last > 0 && next !== last) restoreAnchor();
      last = next;
      setWidth(next);
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
    };
  }, [restoreAnchor]);

  // A language switch mirrors the chrome and reflows the text above the pages: stay put.
  const language = i18n.language;
  const shownLanguage = useRef(language);
  useLayoutEffect(() => {
    if (shownLanguage.current === language) return;
    shownLanguage.current = language;
    restoreAnchor();
  }, [language, restoreAnchor]);

  // Follow the reader: the current page is the one crossing a line near the top.
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const line = window.innerHeight * CURRENT_LINE;
      let page = 1;
      for (let number = 1; number <= count; number += 1) {
        const element = elements.current.get(number);
        if (!element || element.getBoundingClientRect().top > line) break;
        page = number;
      }
      setCurrent(page);
      measureAnchor();
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(frame);
    };
  }, [count, measureAnchor]);

  const commitDraft = () => {
    if (draft !== null && draft.trim() !== '') {
      const page = Number(draft);
      if (Number.isFinite(page)) goTo(page);
    }
    setDraft(null);
  };

  return (
    <div className={styles.viewer}>
      <nav className={styles.toolbar} aria-label={t('viewer.toolbar.label')}>
        <button
          type="button"
          className={styles.button}
          disabled={current <= 1}
          onClick={() => {
            goTo(current - 1);
          }}
        >
          <span className={styles.back}>
            <Icon name="forward" />
          </span>
          {t('viewer.toolbar.previous')}
        </button>
        <span className={styles.position}>
          <label htmlFor={inputId} className={styles.srOnly}>
            {t('viewer.toolbar.pageInput')}
          </label>
          <input
            id={inputId}
            className={styles.pageInput}
            type="number"
            inputMode="numeric"
            min={1}
            max={count}
            value={draft ?? String(current)}
            onFocus={(event) => {
              event.target.select();
            }}
            onChange={(event) => {
              setDraft(event.target.value);
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') commitDraft();
              if (event.key === 'Escape') setDraft(null);
            }}
            onBlur={commitDraft}
          />
          <span>{t('viewer.toolbar.ofPages', { total: format.number(count) })}</span>
        </span>
        <button
          type="button"
          className={styles.button}
          disabled={current >= count}
          onClick={() => {
            goTo(current + 1);
          }}
        >
          {t('viewer.toolbar.next')}
          <Icon name="forward" />
        </button>
        {cited !== null && (
          <button
            type="button"
            className={styles.citedButton}
            onClick={() => {
              goTo(cited);
            }}
          >
            {t('viewer.toolbar.goToCited', { page: format.number(cited) })}
          </button>
        )}
      </nav>

      <div ref={column} className={styles.pages}>
        {pages.map((page, index) => (
          <PdfPage
            key={index + 1}
            page={page}
            number={index + 1}
            cited={cited === index + 1}
            near={near.has(index + 1)}
            width={width}
            register={register}
          />
        ))}
      </div>
    </div>
  );
}
