/** Upload three files at a time (SYSTEM_DESIGN §5.1). */
export const UPLOAD_CONCURRENCY = 3;

export interface TaskPool {
  /** Queue a task; it starts as soon as fewer than `limit` tasks are running. */
  add(task: () => Promise<unknown>): void;
}

/**
 * A first-in, first-out queue that runs at most `limit` tasks at once. A task that fails only
 * frees its slot: the next one starts as usual, so one bad file never stops the others.
 */
export function createPool(limit: number): TaskPool {
  let running = 0;
  const queue: (() => Promise<unknown>)[] = [];

  const next = () => {
    while (running < limit) {
      const task = queue.shift();
      if (!task) return;
      running += 1;
      void Promise.resolve()
        .then(task)
        .catch(() => undefined)
        .finally(() => {
          running -= 1;
          next();
        });
    }
  };

  return {
    add(task) {
      queue.push(task);
      next();
    },
  };
}
