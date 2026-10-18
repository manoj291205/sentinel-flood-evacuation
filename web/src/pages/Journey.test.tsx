import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import Journey from './Journey';
import phases from '../content/phases.json';

afterEach(cleanup);
it('renders the source-backed phase timeline and D-27 limitation', () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Journey /></QueryClientProvider>);
  expect(screen.getByRole('heading', { name: 'How it was built' })).toBeInTheDocument();
  expect(screen.getAllByText('PHASE 27')).toHaveLength(1);
  expect(screen.getByText(/Bars 2 and 4 pass/)).toBeInTheDocument();
  expect(phases.find(row => row.phase === '27')?.artifact_path).toBe('data/eval_results/phase27/analysis.json');
});
