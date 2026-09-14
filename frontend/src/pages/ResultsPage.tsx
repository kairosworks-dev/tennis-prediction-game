import { useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from '../hooks/useApi';
import { useDrawEntries, useDraws, useTournament } from '../hooks/queries';
import { Logo, Problem, Spinner } from '../components/ui';
import { ROUNDS_REACHED } from '../services';
import type { RoundReached } from '../services';

/**
 * Spec 4.5.4 — the outcome grid and Recalculate scores.
 *
 * The only organiser screen in the first pass (decision D14), because it is
 * the one that closes the loop: results in, leaderboard out. Everything else
 * an organiser does is seeded. Authorisation is checked server-side on every
 * call here; the route guard only saves a participant a pointless round trip.
 *
 * Admin views may assume a desktop viewport, so this one is a wide table
 * rather than a phone column.
 */
export function ResultsPage(): ReactNode {
  const { tournamentId = '' } = useParams();
  const api = useApi();
  const queryClient = useQueryClient();
  const detail = useTournament(tournamentId);
  const draws = useDraws(tournamentId);
  const [drawId, setDrawId] = useState<string | null>(null);

  const activeDrawId = drawId ?? draws.data?.[0]?.id;
  const sections = useDrawEntries(tournamentId, activeDrawId);
  const [edits, setEdits] = useState<Record<string, RoundReached>>({});

  const saveGrid = useMutation({
    mutationFn: async () => {
      const rows = (sections.data ?? []).flatMap((section) =>
        section.entries.map((row) => ({
          playerId: row.player.id,
          roundReached: edits[row.player.id] ?? row.roundReached,
          note: null,
        })),
      );
      return api.putDrawOutcomes({
        drawId: activeDrawId ?? '',
        entries: rows.filter(
          (row): row is { playerId: string; roundReached: RoundReached; note: null } =>
            row.roundReached !== null,
        ),
      });
    },
    onSuccess: async () => {
      setEdits({});
      await queryClient.invalidateQueries();
    },
  });

  const recalculate = useMutation({
    mutationFn: () => api.recalculateScores(tournamentId),
    onSuccess: async () => { await queryClient.invalidateQueries(); },
  });

  if (detail.isPending || draws.isPending) {
    return <Spinner label="Loading the game…" />;
  }

  return (
    <div className="mx-auto min-h-dvh max-w-5xl px-6 pb-16">
      <header className="flex items-center gap-4 py-5">
        <Logo />
        <span className="grow" />
        <Link to={`/games/${tournamentId}/bets`} className="text-sm font-semibold text-clay">
          Back to the game
        </Link>
      </header>

      <h1 className="font-display text-4xl">Results</h1>
      <p className="mt-1.5 text-sm text-muted text-pretty">
        {detail.data?.tournament.name}. One grid settles every typed question — set how far each
        player got, save, then recalculate.
      </p>

      <div className="mt-6 flex gap-2">
        {(draws.data ?? []).map((draw) => (
          <button
            key={draw.id}
            type="button"
            onClick={() => { setDrawId(draw.id); setEdits({}); }}
            className={`rounded px-4 py-2.5 text-sm font-semibold ${
              draw.id === activeDrawId ? 'bg-court text-paper' : 'border border-line-strong bg-card text-ink-soft'
            }`}
          >
            {draw.tour} draw · best of {draw.bestOf === 5 ? 'five' : 'three'}
          </button>
        ))}
      </div>

      {sections.isPending && <Spinner label="Loading the draw…" />}
      <Problem error={saveGrid.error ?? recalculate.error ?? sections.error} />

      <div className="mt-5 flex flex-col gap-5">
        {(sections.data ?? []).map((section) => (
          <section key={section.section.id} className="overflow-hidden rounded border border-line bg-card">
            <h2 className="border-b border-line bg-sunk px-4 py-2.5 text-sm font-semibold text-ink-soft">
              Section {section.section.index}
            </h2>
            <table className="w-full text-sm">
              <thead className="sr-only">
                <tr>
                  <th>Seed</th>
                  <th>Player</th>
                  <th>Round reached</th>
                </tr>
              </thead>
              <tbody>
                {section.entries.map((row) => (
                  <tr key={row.entry.id} className="border-b border-line/50 last:border-0">
                    <td className="w-14 px-4 py-2 font-mono text-xs text-faint">
                      {row.entry.seed === null ? '—' : `[${row.entry.seed}]`}
                    </td>
                    <td className="py-2 font-medium">{row.player.fullName}</td>
                    <td className="w-44 px-4 py-2 text-right">
                      <select
                        aria-label={`Round reached by ${row.player.fullName}`}
                        value={edits[row.player.id] ?? row.roundReached ?? ''}
                        onChange={(event) => {
                          setEdits((current) => ({
                            ...current,
                            [row.player.id]: event.target.value as RoundReached,
                          }));
                        }}
                        className="h-9 w-full rounded border border-line-strong bg-paper px-2 font-mono text-xs"
                      >
                        <option value="">not set</option>
                        {ROUNDS_REACHED.map((round) => (
                          <option key={round} value={round}>
                            {round}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ))}
      </div>

      <div className="sticky bottom-0 mt-6 flex items-center gap-3 border-t border-line bg-paper py-4">
        <p className="grow text-sm text-muted">
          {Object.keys(edits).length === 0
            ? 'No unsaved changes.'
            : `${Object.keys(edits).length} unsaved change(s).`}
          {recalculate.isSuccess && ' Scores rebuilt.'}
        </p>
        <button
          type="button"
          disabled={saveGrid.isPending || Object.keys(edits).length === 0}
          onClick={() => { saveGrid.mutate(); }}
          className="h-11 rounded border-[1.5px] border-court px-5 text-sm font-semibold text-court disabled:opacity-50"
        >
          {saveGrid.isPending ? 'Saving…' : 'Save the grid'}
        </button>
        <button
          type="button"
          disabled={recalculate.isPending}
          onClick={() => { recalculate.mutate(); }}
          className="h-11 rounded bg-clay px-5 text-sm font-semibold text-card disabled:opacity-60"
        >
          {recalculate.isPending ? 'Recalculating…' : 'Recalculate scores'}
        </button>
      </div>
    </div>
  );
}
