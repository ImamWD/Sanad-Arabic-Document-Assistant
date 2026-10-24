import { DirectionProvider } from '@radix-ui/react-direction';
import { type QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { type ReactNode, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { createBrowserRouter, RouterProvider } from 'react-router';

import { ProfileLanguage } from './ProfileLanguage';
import { createQueryClient } from './queryClient';
import { routes } from './routes';

interface AppProvidersProps {
  children: ReactNode;
  queryClient: QueryClient;
}

/**
 * Server state, direction and the user's saved language for the whole tree. Radix primitives
 * read the direction from DirectionProvider, which follows i18n.dir() just like <html dir>
 * (app/i18n.ts). A language switch re-renders in place: no provider remounts and no query key
 * contains the language, so nothing is refetched and form state survives.
 */
export function AppProviders({ children, queryClient }: AppProvidersProps) {
  const { i18n } = useTranslation();
  return (
    <QueryClientProvider client={queryClient}>
      <DirectionProvider dir={i18n.dir()}>
        <ProfileLanguage />
        {children}
      </DirectionProvider>
    </QueryClientProvider>
  );
}

export function App() {
  const [queryClient] = useState(createQueryClient);
  const [router] = useState(() => createBrowserRouter(routes));
  return (
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
