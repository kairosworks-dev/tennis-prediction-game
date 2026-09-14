import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ApiProvider } from '../hooks/ApiProvider';
import { LandingPage } from './LandingPage';
import { createTestApiClient } from '../services/testing';
import type { ApiClient } from '../services';

function renderWith(client: ApiClient): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <LandingPage />
        </MemoryRouter>
      </QueryClientProvider>
    </ApiProvider>,
  );
}

/**
 * Spec 4.1 requires the landing page to render without any authenticated call
 * and to degrade gracefully if the teaser query fails. Both are tested here
 * because both are easy to break and invisible until a stranger opens the site.
 */
describe('the landing page', () => {
  it('renders for a visitor who is not signed in', async () => {
    renderWith(createTestApiClient({ signedIn: false }));
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    expect(await screen.findByText(/open for signup/i)).toBeInTheDocument();
  });

  it('shows a neutral state rather than an error when the teaser fails', async () => {
    // The page calls nothing else, so a one-method stub is the whole surface.
    const failing = {
      getNextGame: (): Promise<never> => Promise.reject(new Error('the teaser is down')),
    } as unknown as ApiClient;

    renderWith(failing);
    expect(await screen.findByText(/no game currently open/i)).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
