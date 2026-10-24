import { Navigate, type RouteObject } from 'react-router';

import { AskPage } from '../features/ask/AskPage';
import { LoginPage } from '../features/auth/LoginPage';
import { AppLayout } from './AppLayout';
import { RequireAuth, RequireRole } from './guards';
import { DocumentPage, NotFoundPage, PlaceholderPage } from './pages';
import { PublicLayout } from './PublicLayout';

// No loaders or actions: server state lives in TanStack Query only, so navigation (or a
// language switch) never triggers a fetch by itself. Feature tasks swap in their page here.
export const routes: RouteObject[] = [
  {
    path: '/login',
    element: <PublicLayout />,
    children: [{ index: true, element: <LoginPage /> }],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <Navigate to="/ask" replace /> },
          { path: 'ask', element: <AskPage /> },
          { path: 'library', element: <PlaceholderPage id="library" /> },
          { path: 'documents/:id', element: <DocumentPage /> },
          {
            element: <RequireRole minimum="editor" />,
            children: [{ path: 'upload', element: <PlaceholderPage id="upload" /> }],
          },
          {
            element: <RequireRole minimum="admin" />,
            children: [{ path: 'admin', element: <PlaceholderPage id="admin" /> }],
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
];
