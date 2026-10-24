// Test helpers for the shell: a fake /api and the real route tree in a memory router.
// Users are synthetic and obviously fake (CLAUDE.md rule 9).
import { render } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { vi } from 'vitest';

import type { Me, Role } from '../features/auth/types';
import { AppProviders } from './App';
import { initI18n } from './i18n';
import { createQueryClient } from './queryClient';
import { routes } from './routes';

const TEST_USERS: Record<Role, Pick<Me, 'id' | 'name'>> = {
  viewer: { id: '00000000-0000-4000-8000-000000000001', name: 'ليلى تجريبية' },
  editor: { id: '00000000-0000-4000-8000-000000000002', name: 'Sami Example' },
  admin: { id: '00000000-0000-4000-8000-000000000003', name: 'مدير تجريبي' },
};

export function testUser(role: Role, overrides: Partial<Me> = {}): Me {
  return {
    ...TEST_USERS[role],
    email: `${role}@example.org`,
    role,
    preferred_language: 'ar',
    is_guest: false,
    ...overrides,
  };
}

export const GUEST = testUser('viewer', { name: 'ضيف تجريبي', email: '', is_guest: true });

export function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

export function apiError(status: number, code: string, params: Record<string, unknown> = {}) {
  return json(status, { error: { code, params } });
}

type Handler = (body: unknown) => Response | Promise<Response>;

export interface ApiCall {
  method: string;
  path: string;
  body: unknown;
}

/**
 * Replace fetch with a fake /api. `handlers` maps "METHOD /api/path" to a response; anything
 * else is a 404 NOT_FOUND. `calls` records every request in order.
 */
export function mockApi(handlers: Record<string, Handler>) {
  const calls: ApiCall[] = [];
  const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const method = init?.method ?? 'GET';
    const path = new URL(
      typeof input === 'string' ? input : input instanceof URL ? input.href : input.url,
      'http://sanad.test',
    ).pathname;
    const body: unknown = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined;
    calls.push({ method, path, body });
    const handler = handlers[`${method} ${path}`];
    return handler ? handler(body) : apiError(404, 'NOT_FOUND');
  });
  return { calls, fetchSpy };
}

interface RenderAppOptions {
  path?: string;
  /** Who GET /api/me returns; null means no session (401). */
  user?: Me | null;
  handlers?: Record<string, Handler>;
}

export async function renderApp({ path = '/', user = null, handlers = {} }: RenderAppOptions = {}) {
  const api = mockApi({
    'GET /api/me': () => (user ? json(200, user) : apiError(401, 'UNAUTHENTICATED')),
    ...handlers,
  });
  const i18n = await initI18n();
  const queryClient = createQueryClient();
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const view = render(
    <I18nextProvider i18n={i18n}>
      <AppProviders queryClient={queryClient}>
        <RouterProvider router={router} />
      </AppProviders>
    </I18nextProvider>,
  );
  return { ...view, ...api, i18n, queryClient, router };
}
