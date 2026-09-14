import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useJoinTournament, useLogout, useSession, useTournaments } from '../hooks/queries';
import { Empty, Logo, Problem, Spinner, SurfaceBadge } from '../components/ui';
import { categoryLabel, formatDateRange, timeUntil } from '../components/format';
import type { GameListState, TournamentSummary } from '../services';

const GROUPS: readonly { state: GameListState; label: string; dot: string }[] = [
  { state: 'RUNNING', label: 'Running', dot: 'bg-clay' },
  { state: 'OPEN_FOR_SIGNUP', label: 'Open for signup', dot: 'bg-court' },
  { state: 'FINISHED', label: 'Finished', dot: 'bg-ghost' },
];

/** Spec 4.3 — three states, each card carrying the next relevant deadline. */
export function GamesPage(): ReactNode {
  const session = useSession();
  const tournaments = useTournaments();
  const logout = useLogout();
  const join = useJoinTournament();
  const [joinCode, setJoinCode] = useState('');
  const [codeOpen, setCodeOpen] = useState(false);

  return (
    <div className="phone-shell pb-10">
      <header className="flex items-center gap-3 bg-court px-5 py-4">
        <Logo tone="bone" />
        <span className="grow" />
        <button
          type="button"
          onClick={() => { logout.mutate(); }}
          className="text-xs font-medium text-court-pale underline-offset-2 hover:underline"
        >
          Sign out
        </button>
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-court-light text-[13px] font-semibold text-paper">
          {session.data?.displayName.slice(0, 1).toUpperCase() ?? '?'}
        </span>
      </header>

      <h1 className="px-5 pt-6 font-display text-4xl leading-none">Your games</h1>

      {tournaments.isPending && <Spinner label="Loading your games…" />}
      {tournaments.isError && (
        <div className="px-5 pt-5">
          <Problem error={tournaments.error} />
        </div>
      )}

      {tournaments.data !== undefined &&
        GROUPS.map(({ state, label, dot }) => {
          const rows = tournaments.data.filter((summary) => summary.state === state);
          if (rows.length === 0) {
            return null;
          }
          return (
            <section key={state} className="px-5 pt-7">
              <h2 className="flex items-center gap-2 text-[11px] font-semibold tracking-[0.1em] uppercase text-muted">
                <span className={`h-[7px] w-[7px] rounded-full ${dot}`} />
                {label}
              </h2>
              <div className="mt-3 flex flex-col gap-3">
                {rows.map((summary) => (
                  <GameCard key={summary.tournament.id} summary={summary} onJoin={join} />
                ))}
              </div>
            </section>
          );
        })}

      {tournaments.data?.length === 0 && (
        <div className="px-5 pt-6">
          <Empty>No games yet. The organiser will publish one before the next tournament.</Empty>
        </div>
      )}

      <section className="px-5 pt-6">
        {codeOpen ? (
          <div className="rounded border border-line bg-card p-4">
            <label htmlFor="joinCode" className="text-[13px] font-semibold">
              Join code
            </label>
            <div className="mt-2 flex gap-2">
              <input
                id="joinCode"
                value={joinCode}
                onChange={(event) => { setJoinCode(event.target.value.toUpperCase()); }}
                className="h-11 grow rounded border border-line-strong bg-paper px-3 font-mono text-sm uppercase"
                placeholder="ABC123"
              />
              <button
                type="button"
                disabled={join.isPending}
                onClick={() => {
                  const target = tournaments.data?.find((s) => s.tournament.visibility === 'PRIVATE');
                  join.mutate({ tournamentId: target?.tournament.id ?? '', joinCode });
                }}
                className="h-11 rounded bg-court px-5 text-sm font-semibold text-paper disabled:opacity-60"
              >
                Join
              </button>
            </div>
            <div className="mt-3">
              <Problem error={join.error} />
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => { setCodeOpen(true); }}
            className="flex h-12 w-full items-center justify-center rounded border border-dashed border-line-strong text-sm font-medium text-muted"
          >
            Join a private game with a code
          </button>
        )}
      </section>
    </div>
  );
}

function GameCard({
  summary,
  onJoin,
}: {
  summary: TournamentSummary;
  onJoin: ReturnType<typeof useJoinTournament>;
}): ReactNode {
  const { tournament, state } = summary;
  const finished = state === 'FINISHED';

  return (
    <article
      className={`rounded border p-4 ${
        state === 'RUNNING'
          ? 'border-line border-l-[3px] border-l-clay bg-card shadow-[0_4px_14px_rgb(30_27_22/0.05)]'
          : finished
            ? 'border-line bg-muted-bg'
            : 'border-line bg-card'
      }`}
    >
      <div className="flex items-start gap-2.5">
        <div className="grow">
          <h3 className={`font-display text-2xl leading-tight ${finished ? 'text-ink-soft' : ''}`}>
            {tournament.name}
          </h3>
          <p className="mt-1 text-[13px] text-muted">
            {categoryLabel(tournament.category)} · {formatDateRange(tournament.startDate, tournament.endDate)} ·{' '}
            {tournament.location}
          </p>
        </div>
        <SurfaceBadge surface={tournament.surface} />
      </div>

      {state === 'RUNNING' && (
        <>
          <dl className="mt-4 flex gap-2.5 rounded bg-sunk px-3.5 py-3 text-center">
            <Stat label="Rank" value={summary.userPosition === null ? '—' : `${summary.userPosition}/${summary.participantCount}`} />
            <Stat label="Points" value={summary.userPoints ?? '—'} />
            <Stat label="Playing" value={summary.participantCount} />
          </dl>
          {summary.nextDeadline !== null && (
            <p className="mt-3.5 text-[13px] font-semibold text-clay">
              Next bets close in {timeUntil(summary.nextDeadline)}
            </p>
          )}
          <Link
            to={`/games/${tournament.id}/bets`}
            className="mt-3.5 flex h-12 items-center justify-center rounded bg-court text-[15px] font-semibold text-paper"
          >
            Open the game
          </Link>
        </>
      )}

      {state === 'OPEN_FOR_SIGNUP' && (
        <div className="mt-3.5 flex items-center border-t border-line pt-3.5">
          <p className="grow text-[13px] text-muted">
            {summary.participantCount} joined · closes in {timeUntil(tournament.signupDeadline)}
          </p>
          {summary.participationId === null ? (
            <button
              type="button"
              disabled={onJoin.isPending}
              onClick={() => { onJoin.mutate({ tournamentId: tournament.id }); }}
              className="h-11 rounded border-[1.5px] border-court px-5 text-sm font-semibold text-court disabled:opacity-60"
            >
              Join
            </button>
          ) : (
            <Link to={`/games/${tournament.id}/bets`} className="text-sm font-semibold text-clay">
              Open
            </Link>
          )}
        </div>
      )}

      {finished && (
        <div className="mt-3.5 flex items-center border-t border-line pt-3.5">
          <p className="grow text-[13px] text-muted">
            {summary.userPosition === null
              ? `${summary.participantCount} played`
              : `You placed ${summary.userPosition} of ${summary.participantCount}`}
          </p>
          <Link to={`/games/${tournament.id}/ranking`} className="text-sm font-semibold text-muted underline-offset-2 hover:underline">
            Final table
          </Link>
        </div>
      )}
    </article>
  );
}

function Stat({ label, value }: { label: string; value: string | number }): ReactNode {
  return (
    <div className="grow">
      <dt className="text-[11px] tracking-wide uppercase text-muted">{label}</dt>
      <dd className="mt-0.5 font-mono text-[17px] font-semibold text-court">{value}</dd>
    </div>
  );
}
