import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { setupServer } from 'msw/node';
import { handlers } from '../mocks/handlers';
import Decisions from './Decisions';

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => { cleanup(); server.resetHandlers(); });
afterAll(() => server.close());

function mount(initial = '/decisions') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[initial]}><Decisions /></MemoryRouter></QueryClientProvider>);
}

describe('Decisions & Certificates', () => {
  it('opens a deep-linked migration and filters the list', async () => {
    mount('/decisions?cert=CERT-000126');
    expect(await screen.findByRole('region', { name: 'Decision detail' })).toHaveTextContent('MIGRATION');
    await userEvent.click(screen.getByRole('radio', { name: 'Migration' }));
    expect(screen.getByRole('region', { name: 'Decision list' }).querySelectorAll('button[aria-pressed]')).toHaveLength(1);
  });

  it('reports the field changed by a tamper replay', async () => {
    mount('/decisions?cert=CERT-000127');
    await screen.findByRole('region', { name: 'Decision detail' });
    await userEvent.click(screen.getByRole('checkbox', { name: 'Tamper with forecast (demo)' }));
    await userEvent.click(screen.getByRole('button', { name: 'Replay certificate' }));
    expect(await screen.findByText(/MISMATCH — forecast_hash/)).toBeVisible();
  });
});
