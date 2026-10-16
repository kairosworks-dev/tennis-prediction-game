import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ApiProvider } from '../../hooks/ApiProvider';
import { BetsTab } from './BetsTab';
import { createTestApiClient } from '../../services/testing';
import type { ApiClient, BetGroup } from '../../services';

const HOUR = 3_600_000;

/**
 * Renders the bets tab for a mock game whose open group has the given deadline.
 *
 * The status stays whatever the server says. Hard rule 2: the tab displays the
 * server's effective status and never decides open or locked itself, so these
 * tests move the deadline and leave the status alone.
 */
async function renderWithOpenGroupDueIn(offsetMs: number): Promise<void> {
  const client: ApiClient = createTestApiClient({ signedIn: true });
  let tournamentId: string | undefined;
  for (const summary of await client.listTournaments()) {
    const groups = await client.listBetGroups(summary.tournament.id);
    if (groups.some((group) => group.status === 'OPEN')) {
      tournamentId = summary.tournament.id;
      break;
    }
  }
  if (tournamentId === undefined) {
    throw new Error('the mock has no game with an open group');
  }
  const real = await client.listBetGroups(tournamentId);
  const moved: BetGroup[] = real.map((group) =>
    group.status === 'OPEN'
      ? { ...group, deadline: new Date(Date.now() + offsetMs).toISOString() }
      : group,
  );
  vi.spyOn(client, 'listBetGroups').mockResolvedValue(moved);

  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <BetsTab tournamentId={tournamentId} />
        </MemoryRouter>
      </QueryClientProvider>
    </ApiProvider>,
  );
}

describe('the bets tab deadline line', () => {
  it('counts down while the deadline is ahead', async () => {
    await renderWithOpenGroupDueIn(5 * HOUR);
    expect(await screen.findByText(/^\d+h \d+m left$/)).toBeInTheDocument();
  });

  it('reads as closed, never "closed left", once the deadline has passed in the browser', async () => {
    await renderWithOpenGroupDueIn(-HOUR);
    expect(await screen.findByText('Closed')).toBeInTheDocument();
    expect(screen.queryByText(/closed left/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\bleft$/)).not.toBeInTheDocument();
  });
});
