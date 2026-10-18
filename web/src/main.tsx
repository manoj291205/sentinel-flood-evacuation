import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { SessionProvider } from './live/sessionStore';
import './tokens.css';

async function start() {
  if (import.meta.env.VITE_API_MOCK === '1') {
    const { worker } = await import('./mocks/browser');
    await worker.start({ onUnhandledRequest: 'bypass' });
  }
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 2000 } } });
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter><SessionProvider><App /></SessionProvider></BrowserRouter>
      </QueryClientProvider>
    </React.StrictMode>,
  );
}

void start();
