import { useQueries } from '@tanstack/react-query';
import { useApi } from './useApi';
import { keys } from './queries';
import { useDraws } from './queries';
import type { DrawSectionWithEntries, TournamentId } from '../services';

/**
 * Player ids resolve to names through the draws, which the API already
 * exposes. There is no separate player lookup on the first-pass contract, and
 * adding one just to render a name would mean an endpoint with no other
 * purpose.
 */
export function usePlayerNames(tournamentId: TournamentId): (playerId: string) => string {
  const api = useApi();
  const draws = useDraws(tournamentId);

  const results = useQueries({
    queries: (draws.data ?? []).map((draw) => ({
      queryKey: keys.drawEntries(tournamentId, draw.id),
      queryFn: (): Promise<readonly DrawSectionWithEntries[]> =>
        api.listDrawEntries(tournamentId, draw.id),
    })),
  });

  const names = new Map<string, string>();
  for (const result of results) {
    for (const section of result.data ?? []) {
      for (const row of section.entries) {
        names.set(row.player.id, row.player.fullName);
      }
    }
  }

  return (playerId: string): string => names.get(playerId) ?? playerId;
}
