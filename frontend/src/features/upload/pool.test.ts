import { describe, expect, it } from 'vitest';

import { createPool } from './pool';

function deferred() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('createPool', () => {
  it('runs at most three tasks at once, in the order they were added', async () => {
    const pool = createPool(3);
    const tasks = Array.from({ length: 5 }, () => deferred());
    const started: number[] = [];
    tasks.forEach((task, i) => {
      pool.add(() => {
        started.push(i);
        return task.promise;
      });
    });
    await tick();
    expect(started).toEqual([0, 1, 2]);

    tasks[1]?.resolve();
    await tick();
    expect(started).toEqual([0, 1, 2, 3]);

    tasks[0]?.resolve();
    await tick();
    expect(started).toEqual([0, 1, 2, 3, 4]);
  });

  it('a failing task only frees its slot: the rest still run', async () => {
    const pool = createPool(1);
    const done: string[] = [];
    pool.add(() => Promise.reject(new Error('corrupt file')));
    pool.add(() => {
      throw new Error('thrown synchronously');
    });
    pool.add(async () => {
      done.push('good file');
      await Promise.resolve();
    });
    await tick();
    await tick();
    expect(done).toEqual(['good file']);
  });
});
