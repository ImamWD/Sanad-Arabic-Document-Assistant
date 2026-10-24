import './styles/global.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { I18nextProvider } from 'react-i18next';

import { App } from './app/App';
import { initI18n } from './app/i18n';

const root = document.getElementById('root');
if (!root) throw new Error('#root element missing from index.html');

const i18n = await initI18n();

createRoot(root).render(
  <StrictMode>
    <I18nextProvider i18n={i18n}>
      <App />
    </I18nextProvider>
  </StrictMode>,
);
