import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
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
  it('gives populated research bars valid accessible names and retains the source value', async () => {
    server.use(http.get('/api/evidence', () => HttpResponse.json({ items: [{
      id: 'p10-ui-fixture', group: 'Historical', label: 'UI fixture measure',
      value: 1, display: '1.000', unit: 'fixture', source_path: 'test-only.json',
    }] })));
    mount(<Evidence />);
    const chart = await screen.findByRole('img', { name: 'Phase 10 · planner comparison artifact values as bars' });
    expect(within(chart).getByRole('img', { name: 'UI fixture measure: 1.000' })).toBeVisible();
    expect(chart.querySelector('rect[aria-label]')).toBeNull();
    expect(within(chart).getByText('1.000')).toBeVisible();
  });

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
