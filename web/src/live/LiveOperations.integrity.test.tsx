import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest';
import { handlers } from '../mocks/handlers';
import { SessionProvider } from './sessionStore';
import LiveOperations from './LiveOperations';
import App from '../App';

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => { cleanup(); sessionStorage.clear(); server.resetHandlers(); });
afterAll(() => server.close());

it('shows the current engine clock and closures while retaining the reviewed decision step', async () => {
  server.use(http.post('/api/sessions/:id/decisions', () => HttpResponse.json({
    audit_record: { decision: 'ACCEPT' }, certificates: [{ cert_id: 'CERT-RESULT', kind: 'HOLD' }], rechecks: [],
    state: { current_timestep: 1, closed_edge_svg_path: 'M13 13L14 14', kpis: { waiting: 100, in_transit: 0, safe: 0, certificates_issued: 1 } },
  })));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/live']}><SessionProvider><App /></SessionProvider></MemoryRouter>
  </QueryClientProvider>);
  await userEvent.click(screen.getByRole('button', { name: 'Start' }));
  const bar = screen.getByRole('region', { name: 'Operator decides' });
  await userEvent.click(await within(bar).findByRole('button', { name: 'Accept' }));
  expect(await screen.findByText(/LIVE SESSION .* step 1\//)).toBeVisible();
  expect(screen.getByText('Step 1 · RESULT')).toBeVisible();
  expect(within(bar).getByText('REVIEWED DECISION · step 0')).toBeVisible();
  expect(screen.getByRole('img', { name: /Live certified session:/ }).querySelector('path[d="M13 13L14 14"]')).toBeTruthy();
});

it('opens fresh in live mode and changes the header and controls together when mode changes', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={['/live']}><SessionProvider><App /></SessionProvider></MemoryRouter>
  </QueryClientProvider>);
  expect(screen.getByRole('radio', { name: 'Live session' })).toBeChecked();
  expect(await screen.findByText('LIVE ENGINE · ready to start')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Start' })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Run demo' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Reset' })).not.toBeInTheDocument();
  expect(screen.queryByText('Recorded walkthrough ready')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('radio', { name: 'Guided demo' }));
  expect(await screen.findByText(/RECORDED WALKTHROUGH · t =/)).toBeVisible();
  expect(await screen.findByRole('button', { name: 'Run demo' })).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Start' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('radio', { name: 'Live session' }));
  expect(screen.getByText('LIVE ENGINE · ready to start')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Run demo' })).not.toBeInTheDocument();
});

it('the LIVE ENGINE selector retains the command centre and explicit rule status', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><SessionProvider><LiveOperations /></SessionProvider></MemoryRouter>
  </QueryClientProvider>);
  await userEvent.click(screen.getByRole('radio', { name: 'Guided demo' }));
  await userEvent.click(screen.getByRole('radio', { name: 'Live session' }));
  expect(screen.getByRole('radio', { name: 'Live session' })).toBeChecked();
  await userEvent.click(screen.getByRole('button', { name: 'Start' }));
  const bar = screen.getByRole('region', { name: 'Operator decides' });
  expect(await within(bar).findByRole('button', { name: 'Accept' })).toBeVisible();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByText(/No document-derived rule is mandatory/)).toBeVisible();
});
