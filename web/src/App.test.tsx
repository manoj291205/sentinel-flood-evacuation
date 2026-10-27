import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import App from './App';
import { handlers } from './mocks/handlers';

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
afterEach(() => { cleanup(); localStorage.removeItem('sentinel-theme'); });

describe('console shell', () => {
  it('defaults to Night and exposes a keyboard skip link to the main landmark', async () => {
    localStorage.removeItem('sentinel-theme');
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><App /></MemoryRouter></QueryClientProvider>);
    expect(screen.getByRole('main').closest('[data-theme]')).toHaveAttribute('data-theme', 'Night');
    const skip = screen.getByRole('link', { name: 'Skip to main content' });
    expect(skip).toHaveAttribute('href', '#console-content');
    await userEvent.tab();
    expect(skip).toHaveFocus();
  });

  it('honors a saved Day preference rather than overriding the operator theme', () => {
    localStorage.setItem('sentinel-theme', 'Day');
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><App /></MemoryRouter></QueryClientProvider>);
    expect(screen.getByRole('main').closest('[data-theme]')).toHaveAttribute('data-theme', 'Day');
    localStorage.removeItem('sentinel-theme');
  });

  it('keeps five established navigation links and the honesty banner visible while toggling theme', async () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/']}><App /></MemoryRouter></QueryClientProvider>);
    expect(screen.getByRole('navigation', { name: 'Main' }).querySelectorAll('a')).toHaveLength(5);
    expect(screen.getByRole('navigation', { name: 'Showcase' }).querySelectorAll('a')).toHaveLength(2);
    expect(screen.getByRole('note')).toHaveTextContent('NOT OPERATIONALLY VALIDATED');
    const app = screen.getByRole('note').closest('[data-theme]');
    const before = app?.getAttribute('data-theme');
    await userEvent.click(screen.getByRole('button', { name: /theme/i }));
    expect(app?.getAttribute('data-theme')).not.toBe(before);
  });
});
