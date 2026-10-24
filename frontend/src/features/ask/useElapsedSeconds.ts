import { useEffect, useState } from 'react';

const TICK_MS = 500;

/**
 * Whole seconds since `since` (ms since the epoch), ticking while `since` is set. Driven by
 * Date.now() and timers, so fake clocks (vitest, Playwright's page.clock) control it.
 */
export function useElapsedSeconds(since: number | null): number {
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    if (since === null) return;
    const tick = () => {
      setNow(Date.now());
    };
    const first = setTimeout(tick, 0);
    const timer = setInterval(tick, TICK_MS);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [since]);

  if (since === null || now === null) return 0;
  return Math.max(0, Math.floor((now - since) / 1000));
}
