import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { setupServer } from 'msw/node';
import { handlers } from '../mocks/handlers';
import Overview from './Overview';
import Evidence from './Evidence';
import System from './System';

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => { cleanup(); server.resetHandlers(); });
afterAll(() => server.close());

function mount(page: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{page}</MemoryRouter></QueryClientProvider>);
}

describe('Wave B overview and evidence pages', () => {
  it('takes ledger values from the demo response and links to the latest certificate', async () => {
    mount(<Overview />);
    expect(await screen.findByRole('link', { name: 'CERT-000128' })).toHaveAttribute('href', '/decisions?cert=CERT-000128');
    expect(screen.getByRole('heading', { name: 'Population ledger' })).toBeVisible();
    expect(screen.getByText('Not in demo state')).toBeVisible();
  });

  it('shows missing evidence with its manifest path and reason', async () => {
    mount(<Evidence />);
    const source = await screen.findByText('data/eval_results/phase27/analysis.json');
    expect(source.closest('tr')).toHaveTextContent('not produced yet in mock mode');
    expect(source.closest('tr')).toHaveTextContent('-');
  });

  it('labels fixture devices offline and leaves physical latency pending', async () => {
    mount(<System />);
    expect(await screen.findByText('sim-shelter-01')).toBeVisible();
    expect(screen.getByText(/No physical bench result yet/)).toBeVisible();
    expect(screen.getByText('No commands yet')).toBeVisible();
  });
});
