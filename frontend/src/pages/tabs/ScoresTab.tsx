import type { ReactNode } from 'react';
import { useScoreBreakdown } from '../../hooks/queries';
import { usePlayerNames } from '../../hooks/usePlayerNames';
import { Empty, Problem, Spinner } from '../../components/ui';
import { describePayload } from '../payloadText';
import type { BetGroupScoreBlock } from '../../services';

/** Spec 4.4.3 — every question with the prediction, the answer, points and why. */
export function ScoresTab({ tournamentId }: { tournamentId: string }): ReactNode {
  const scores = useScoreBreakdown(tournamentId);
  const nameOf = usePlayerNames(tournamentId);

  if (scores.isPending) {
    return <Spinner label="Adding up your points…" />;
  }
  if (scores.isError) {
    return (
      <div className="px-5 pt-5">
        <Problem error={scores.error} />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-3.5 border-b border-line bg-card px-5 py-5">
        <div>
          <p className="font-display text-4xl leading-none text-court">{scores.data.total}</p>
          <p className="mt-0.5 text-[11px] tracking-wider uppercase text-muted">points</p>
        </div>
        <span className="h-10 w-px bg-line" />
        <p className="grow text-sm text-muted">
          {scores.data.position === null
            ? 'Not ranked yet'
            : `${scores.data.position} of ${scores.data.participantCount}`}
        </p>
      </div>

      <div className="flex flex-col gap-3 px-5 pt-5">
        {scores.data.groups.length === 0 && <Empty>No bet groups yet.</Empty>}
        {scores.data.groups.map((block) => (
          <GroupBlock key={block.betGroup.id} block={block} nameOf={nameOf} />
        ))}
      </div>
    </div>
  );
}

function GroupBlock({
  block,
  nameOf,
}: {
  block: BetGroupScoreBlock;
  nameOf: (playerId: string) => string;
}): ReactNode {
  const answered = block.rows.filter((row) => row.ownPayload !== null);

  return (
    <section className="overflow-hidden rounded border border-line bg-card">
      <header className="flex items-center gap-2.5 border-b border-line bg-sunk px-4 py-3.5">
        <h2 className="grow text-sm font-semibold text-ink-soft">{block.betGroup.title}</h2>
        {block.betGroup.status === 'OPEN' ? (
          <span className="rounded bg-clay-soft px-2 py-1 text-[10px] font-semibold tracking-wider uppercase text-clay-dark">
            Open
          </span>
        ) : (
          <span className="font-mono text-[15px] font-semibold text-court">
            {block.subtotal}
            <span className="text-[11px] text-faint">pts</span>
          </span>
        )}
      </header>

      {answered.length === 0 ? (
        <p className="px-4 py-4 text-[13px] text-faint">Nothing answered in this group yet.</p>
      ) : (
        <ul>
          {answered.map((row) => (
            <li key={row.question.id} className="border-b border-line/50 px-4 py-3.5 last:border-0">
              <div className="flex items-baseline gap-2.5">
                <p className="grow text-sm font-semibold">{row.question.prompt}</p>
                <span
                  className={`font-mono text-sm font-semibold ${
                    row.points === null ? 'text-faint' : row.points > 0 ? 'text-court' : 'text-ghost'
                  }`}
                >
                  {row.points ?? '—'}
                </span>
              </div>
              <p className="mt-1.5 text-[13px] text-muted">
                <span className="text-faint">You said </span>
                {describePayload(row.ownPayload, nameOf)}
              </p>
              {row.correctAnswer !== null && (
                <p className="mt-0.5 text-[13px] text-muted">
                  <span className="text-faint">Result </span>
                  <span className="font-medium text-court">{describePayload(row.correctAnswer, nameOf)}</span>
                </p>
              )}
              {row.reason !== null && (
                <p className="mt-1.5 text-[13px] leading-relaxed text-muted text-pretty">{row.reason}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
