import { Navigate, type RouteObject } from 'react-router';

import { AdminPage } from '../features/admin/AdminPage';
import { AskPage } from '../features/ask/AskPage';
import { LoginPage } from '../features/auth/LoginPage';
import { LibraryPage } from '../features/library/LibraryPage';
import { UploadPage } from '../features/upload/UploadPage';
import { ViewerPage } from '../features/viewer/ViewerPage';
import { AppLayout } from './AppLayout';
import { RequireAuth, RequireRole } from './guards';
import { NotFoundPage, PlaceholderPage } from './pages';
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
          { path: 'library', element: <LibraryPage /> },
          { path: 'documents/:id', element: <ViewerPage /> },
          {
            element: <RequireRole minimum="editor" />,
            children: [{ path: 'upload', element: <UploadPage /> }],
          },
          {
            element: <RequireRole minimum="admin" />,
            children: [{ path: 'admin', element: <AdminPage /> }],
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
];
