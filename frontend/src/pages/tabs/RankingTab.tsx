import { useState, type ReactNode } from 'react';
import { useRanking } from '../../hooks/queries';
import { Empty, Problem, Spinner } from '../../components/ui';

/** Spec 4.4.4 — ties share a position and the next position skips (D13). */
export function RankingTab({ tournamentId }: { tournamentId: string }): ReactNode {
  const ranking = useRanking(tournamentId);
  const [expanded, setExpanded] = useState<string | null>(null);

  if (ranking.isPending) {
    return <Spinner label="Loading the leaderboard…" />;
  }
  if (ranking.isError) {
    return (
      <div className="px-5 pt-5">
        <Problem error={ranking.error} />
      </div>
    );
  }
  if (ranking.data.length === 0) {
    return (
      <div className="px-5 pt-5">
        <Empty>Nobody has scored yet. The table fills in when the first group settles.</Empty>
      </div>
    );
  }

  return (
    <div className="px-5 pt-5">
      <div className="flex gap-2.5 px-4 pb-2 text-[10px] tracking-wider uppercase text-faint">
        <span className="w-6 shrink-0">#</span>
        <span className="grow">Player</span>
        <span className="w-9 text-right">Last</span>
        <span className="w-10 text-right">Total</span>
      </div>

      <ol className="overflow-hidden rounded border border-line bg-card">
        {ranking.data.map((entry) => {
          const open = expanded === entry.participationId;
          return (
            <li
              key={entry.participationId}
              className={`border-b border-line/60 last:border-0 ${
                entry.isCurrentUser ? 'border-l-[3px] border-l-clay bg-clay-soft' : ''
              }`}
            >
              <button
                type="button"
                onClick={() => { setExpanded(open ? null : entry.participationId); }}
                className="flex w-full items-center gap-2.5 px-4 py-3.5 text-left"
                aria-expanded={open}
              >
                <span
                  className={`w-6 shrink-0 font-mono text-[15px] font-semibold ${
                    entry.position === 1 ? 'text-clay' : entry.isCurrentUser ? 'text-clay-dark' : 'text-ink-soft'
                  }`}
                >
                  {entry.position}
                </span>
                <span className={`grow text-[15px] ${entry.isCurrentUser ? 'font-bold' : 'font-semibold'}`}>
                  {entry.displayName}
                </span>
                <Movement movement={entry.movement} />
                <span className="w-9 text-right font-mono text-sm text-muted">{entry.lastGroupPoints}</span>
                <span className="w-10 text-right font-mono text-base font-semibold text-court">
                  {entry.totalPoints}
                </span>
              </button>

              {open && (
                <dl className="flex flex-wrap gap-2 px-4 pb-3.5">
                  {entry.perGroupPoints.map((group) => (
                    <div key={group.betGroupId} className="grow rounded bg-card px-2.5 py-2">
                      <dt className="text-[10px] tracking-wide uppercase text-faint">{group.title}</dt>
                      <dd className="mt-0.5 font-mono text-sm font-semibold text-court">{group.points}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </li>
          );
        })}
      </ol>

      <p className="mt-4 text-xs leading-relaxed text-faint text-pretty">
        Ties share a position and the next one skips. Total points is the only criterion.
      </p>
    </div>
  );
}

function Movement({ movement }: { movement: number | null }): ReactNode {
  if (movement === null || movement === 0) {
    return <span className="h-[1.5px] w-3 bg-line-strong" aria-label="unchanged" />;
  }
  const up = movement > 0;
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-3.5 w-3.5"
      fill="none"
      stroke={up ? '#1c4034' : '#c0392b'}
      strokeWidth="2.2"
      aria-label={up ? `up ${movement}` : `down ${-movement}`}
    >
      {up ? <path d="M12 18V7M12 6l-5 5M12 6l5 5" /> : <path d="M12 6v11M12 18l-5-5M12 18l5-5" />}
    </svg>
  );
}
