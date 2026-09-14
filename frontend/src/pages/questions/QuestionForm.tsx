import { useState, type ReactNode } from 'react';
import { useDraws, useDrawEntries, usePutPrediction } from '../../hooks/queries';
import { Problem } from '../../components/ui';
import { legalSetScores } from '../../services';
import type {
  DrawSectionWithEntries, MatchFormat, Prediction, PredictionPayload, Question, SetScore,
} from '../../services';
import { PlayerChips, SectionPicker } from './pickers';

/**
 * One question, rendered by kind.
 *
 * The frontend narrows what can be chosen — a breakout picker only offers
 * unseeded entrants, a semi-final picker only offers your own quarter-finalists
 * — so the common mistakes are unreachable rather than rejected. That is user
 * experience, not enforcement: the service layer validates every payload again
 * and its answer is the one that counts (AGENTS.md rule 2).
 */
export function QuestionForm({
  tournamentId,
  question,
  existing,
  allPredictions,
  questions,
}: {
  tournamentId: string;
  question: Question;
  existing: PredictionPayload | null;
  allPredictions: readonly Prediction[];
  questions: readonly Question[];
}): ReactNode {
  const entries = useDrawEntries(tournamentId, question.drawId ?? undefined);
  const draws = useDraws(tournamentId);
  const save = usePutPrediction(tournamentId);
  const [draft, setDraft] = useState<PredictionPayload | null>(existing);

  const sections: readonly DrawSectionWithEntries[] = entries.data ?? [];
  const allEntries = sections.flatMap((section) => section.entries);

  /** The answer this participant gave to a sibling typed question in this draw. */
  const sibling = (kind: Question['kind']): PredictionPayload | null => {
    const match = questions.find((q) => q.kind === kind && q.drawId === question.drawId);
    if (match === undefined) {
      return null;
    }
    return allPredictions.find((p) => p.questionId === match.id)?.payload ?? null;
  };

  const poolFrom = (payload: PredictionPayload | null): readonly string[] => {
    if (payload === null) return [];
    if (payload.kind === 'QF_PICKS') return payload.picks.map((p) => p.playerId);
    if (payload.kind === 'SF_PICKS' || payload.kind === 'FINALIST_PICKS') return payload.playerIds;
    return [];
  };

  const submit = (asDraft: boolean): void => {
    if (draft === null) return;
    save.mutate({ tournamentId, questionId: question.id, payload: draft, asDraft });
  };

  return (
    <div className="px-4 py-4">
      <div className="flex items-baseline gap-2">
        <h3 className="grow text-sm font-semibold text-pretty">{question.prompt}</h3>
        <span className="shrink-0 font-mono text-[11px] text-faint">{question.pointsHint}</span>
      </div>

      <div className="mt-3">
        {question.kind === 'QF_PICKS' && (
          <SectionPicker
            sections={sections}
            value={draft?.kind === 'QF_PICKS' ? draft.picks : []}
            onChange={(picks) => { setDraft({ kind: 'QF_PICKS', picks }); }}
          />
        )}

        {question.kind === 'SF_PICKS' && (
          <PlayerChips
            pool={poolFrom(sibling('QF_PICKS'))}
            entries={allEntries}
            selected={draft?.kind === 'SF_PICKS' ? draft.playerIds : []}
            max={4}
            emptyHint="Answer the quarter-finalists question first."
            onChange={(playerIds) => { setDraft({ kind: 'SF_PICKS', playerIds }); }}
          />
        )}

        {question.kind === 'FINALIST_PICKS' && (
          <PlayerChips
            pool={poolFrom(sibling('SF_PICKS'))}
            entries={allEntries}
            selected={draft?.kind === 'FINALIST_PICKS' ? draft.playerIds : []}
            max={2}
            emptyHint="Answer the semi-finalists question first."
            onChange={(playerIds) => { setDraft({ kind: 'FINALIST_PICKS', playerIds }); }}
          />
        )}

        {question.kind === 'CHAMPION' && (
          <PlayerChips
            pool={poolFrom(sibling('FINALIST_PICKS'))}
            entries={allEntries}
            selected={draft?.kind === 'CHAMPION' ? [draft.playerId] : []}
            max={1}
            emptyHint="Answer the finalists question first."
            onChange={(playerIds) => {
              const playerId = playerIds[0];
              setDraft(playerId === undefined ? null : { kind: 'CHAMPION', playerId });
            }}
          />
        )}

        {question.kind === 'UNDERPERFORMER' && (
          <PlayerChips
            pool={allEntries.filter((e) => e.entry.seed !== null && e.entry.seed <= 10).map((e) => e.player.id)}
            entries={allEntries}
            selected={draft?.kind === 'UNDERPERFORMER' ? [draft.playerId] : []}
            max={1}
            showSeeds
            emptyHint="No seeded entrants in this draw yet."
            onChange={(playerIds) => {
              const playerId = playerIds[0];
              setDraft(playerId === undefined ? null : { kind: 'UNDERPERFORMER', playerId });
            }}
          />
        )}

        {question.kind === 'BREAKOUT' && (
          <PlayerChips
            pool={allEntries.filter((e) => e.entry.seed === null).slice(0, 24).map((e) => e.player.id)}
            entries={allEntries}
            selected={draft?.kind === 'BREAKOUT' ? [draft.playerId] : []}
            max={1}
            emptyHint="No unseeded entrants in this draw yet."
            onChange={(playerIds) => {
              const playerId = playerIds[0];
              setDraft(playerId === undefined ? null : { kind: 'BREAKOUT', playerId });
            }}
          />
        )}

        {question.answerType === 'MATCH_RESULT' && question.matchup !== null && (
          <MatchResult
            matchup={question.matchup}
            entries={allEntries}
            bestOf={draws.data?.find((d) => d.id === question.drawId)?.bestOf ?? 3}
            value={draft?.kind === 'GENERIC_MATCH_RESULT' ? draft : null}
            onChange={(next) => { setDraft(next); }}
          />
        )}

        {question.answerType === 'INTEGER' && (
          <IntegerStepper
            value={draft?.kind === 'GENERIC_INTEGER' ? draft.value : 0}
            onChange={(value) => { setDraft({ kind: 'GENERIC_INTEGER', value }); }}
          />
        )}
      </div>

      {save.isError && (
        <div className="mt-3">
          <Problem error={save.error} />
        </div>
      )}

      <div className="mt-3.5 flex gap-2.5">
        <button
          type="button"
          onClick={() => { submit(true); }}
          disabled={draft === null || save.isPending}
          className="h-12 grow rounded border-[1.5px] border-line-strong text-sm font-semibold text-ink-soft disabled:opacity-50"
        >
          Save draft
        </button>
        <button
          type="button"
          onClick={() => { submit(false); }}
          disabled={draft === null || save.isPending}
          className="h-12 grow rounded bg-clay text-sm font-semibold text-card disabled:opacity-50"
        >
          {save.isSuccess ? 'Submitted' : 'Submit'}
        </button>
      </div>
    </div>
  );
}

function MatchResult({
  matchup,
  entries,
  bestOf,
  value,
  onChange,
}: {
  matchup: readonly [string, string];
  entries: readonly DrawSectionWithEntries['entries'][number][];
  bestOf: MatchFormat;
  value: { winnerId: string; setScore: SetScore } | null;
  onChange: (payload: PredictionPayload) => void;
}): ReactNode {
  // Legal scores follow the draw's own match format (spec 5.3).
  const scores = legalSetScores(bestOf);

  const nameOf = (playerId: string): string =>
    entries.find((e) => e.player.id === playerId)?.player.fullName ?? playerId;
  const seedOf = (playerId: string): number | null =>
    entries.find((e) => e.player.id === playerId)?.entry.seed ?? null;

  return (
    <>
      <div className="flex gap-2.5">
        {matchup.map((playerId) => {
          const chosen = value?.winnerId === playerId;
          const seed = seedOf(playerId);
          return (
            <button
              key={playerId}
              type="button"
              onClick={() => {
                onChange({
                  kind: 'GENERIC_MATCH_RESULT',
                  winnerId: playerId,
                  setScore: value?.setScore ?? (scores[0] ?? '2-0'),
                });
              }}
              className={`grow basis-0 rounded border px-3 py-3.5 text-left ${
                chosen ? 'border-2 border-clay bg-clay-soft' : 'border-line-strong bg-card'
              }`}
            >
              <span className="font-mono text-[11px] font-semibold text-muted">
                {seed === null ? '—' : `[${seed}]`}
              </span>
              <span className="mt-1 block text-[15px] leading-tight font-semibold">{nameOf(playerId)}</span>
            </button>
          );
        })}
      </div>

      <p className="mt-3.5 text-xs text-muted">
        {value === null ? 'Set score — pick a winner first' : `Set score — best of ${bestOf === 5 ? 'five' : 'three'}`}
      </p>
      <div className="mt-2 flex gap-2">
        {scores.map((score) => (
          <button
            key={score}
            type="button"
            disabled={value === null}
            onClick={() => {
              if (value !== null) {
                onChange({ kind: 'GENERIC_MATCH_RESULT', winnerId: value.winnerId, setScore: score });
              }
            }}
            className={`h-12 grow rounded border font-mono text-[15px] font-semibold ${
              value?.setScore === score
                ? 'border-court bg-court text-paper'
                : value === null
                  ? 'border-line bg-sunk text-ghost'
                  : 'border-line-strong bg-card text-ink-soft'
            }`}
          >
            {score}
          </button>
        ))}
      </div>
    </>
  );
}

function IntegerStepper({ value, onChange }: { value: number; onChange: (value: number) => void }): ReactNode {
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        aria-label="one fewer"
        onClick={() => { onChange(Math.max(0, value - 1)); }}
        className="h-12 w-12 rounded border border-line-strong bg-card text-xl text-ink-soft"
      >
        −
      </button>
      <output className="flex h-12 grow items-center justify-center rounded border border-line-strong bg-card font-mono text-lg font-semibold">
        {value}
      </output>
      <button
        type="button"
        aria-label="one more"
        onClick={() => { onChange(value + 1); }}
        className="h-12 w-12 rounded border border-line-strong bg-card text-xl text-ink-soft"
      >
        +
      </button>
    </div>
  );
}
