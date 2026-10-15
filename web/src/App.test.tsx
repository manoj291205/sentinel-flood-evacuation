import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import App from './App';

describe('console shell', () => {
  it('keeps five routes and the honesty banner visible while toggling theme', async () => {
    render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);
    expect(screen.getByRole('navigation', { name: 'Main' }).querySelectorAll('a')).toHaveLength(5);
    expect(screen.getByRole('note')).toHaveTextContent('NOT OPERATIONALLY VALIDATED');
    const app = screen.getByRole('note').closest('[data-theme]');
    const before = app?.getAttribute('data-theme');
    await userEvent.click(screen.getByRole('button', { name: /theme/i }));
    expect(app?.getAttribute('data-theme')).not.toBe(before);
  });
});
