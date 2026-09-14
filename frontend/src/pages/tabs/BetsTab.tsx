import { useMemo, useState, type ReactNode } from 'react';
import { useBetGroups, useOwnPredictions, useQuestions } from '../../hooks/queries';
import { Empty, Problem, Spinner } from '../../components/ui';
import { timeUntil } from '../../components/format';
import { QuestionForm } from '../questions/QuestionForm';
import { describePayload } from '../payloadText';
import { usePlayerNames } from '../../hooks/usePlayerNames';
import type { BetGroup } from '../../services';

/** Spec 4.4.2 — every bet group ordered by deadline, the open one expanded. */
export function BetsTab({ tournamentId }: { tournamentId: string }): ReactNode {
  const groups = useBetGroups(tournamentId);
  const predictions = useOwnPredictions(tournamentId);
  const [expanded, setExpanded] = useState<string | null>(null);

  const openGroup = groups.data?.find((group) => group.status === 'OPEN');
  const activeId = expanded ?? openGroup?.id ?? null;

  if (groups.isPending) {
    return <Spinner label="Loading the bets…" />;
  }
  if (groups.isError) {
    return (
      <div className="px-5 pt-5">
        <Problem error={groups.error} />
      </div>
    );
  }
  if (groups.data.length === 0) {
    return (
      <div className="px-5 pt-5">
        <Empty>The organiser has not opened any bets yet.</Empty>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2.5 px-5 pt-5">
      {groups.data.map((group) => (
        <GroupCard
          key={group.id}
          group={group}
          tournamentId={tournamentId}
          expanded={activeId === group.id}
          onToggle={() => { setExpanded(activeId === group.id ? '' : group.id); }}
          answeredCount={
            predictions.data?.filter((prediction) =>
              prediction.questionId.startsWith(group.id),
            ).length ?? 0
          }
        />
      ))}
    </div>
  );
}

function GroupCard({
  group,
  tournamentId,
  expanded,
  onToggle,
  answeredCount,
}: {
  group: BetGroup;
  tournamentId: string;
  expanded: boolean;
  onToggle: () => void;
  answeredCount: number;
}): ReactNode {
  const open = group.status === 'OPEN';
  const upcoming = group.status === 'DRAFT';

  return (
    <section
      className={`overflow-hidden rounded border ${
        open
          ? 'border-line border-t-[3px] border-t-clay bg-card shadow-[0_6px_20px_rgb(30_27_22/0.07)]'
          : upcoming
            ? 'border-dashed border-line-strong'
            : 'border-line bg-muted-bg'
      }`}
    >
      <button
        type="button"
        onClick={onToggle}
        disabled={upcoming}
        aria-expanded={expanded}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left disabled:cursor-default"
      >
        {!open && !upcoming && (
          <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0" fill="none" stroke="#9a8b76" strokeWidth="1.7">
            <rect x="4.5" y="10.5" width="15" height="9.5" rx="2" />
            <path d="M8 10.5V7.8a4 4 0 018 0v2.7" />
          </svg>
        )}
        <div className="grow">
          <h2 className={open ? 'font-display text-2xl leading-tight' : 'text-sm font-semibold text-ink-soft'}>
            {group.title}
          </h2>
          <p className={`mt-0.5 text-xs ${open ? 'font-mono font-semibold text-clay' : 'text-faint'}`}>
            {open
              ? `${timeUntil(group.deadline)} left`
              : upcoming
                ? 'Not open yet'
                : `Locked · ${answeredCount} answered`}
          </p>
        </div>
        {open && (
          <span className="rounded bg-clay-soft px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase text-clay-dark">
            Open
          </span>
        )}
      </button>

      {expanded && !upcoming && <GroupQuestions tournamentId={tournamentId} group={group} />}
    </section>
  );
}

function GroupQuestions({ tournamentId, group }: { tournamentId: string; group: BetGroup }): ReactNode {
  const questions = useQuestions(tournamentId, group.id);
  const predictions = useOwnPredictions(tournamentId);
  const nameOf = usePlayerNames(tournamentId);
  const editable = group.status === 'OPEN';

  const byQuestion = useMemo(
    () => new Map((predictions.data ?? []).map((prediction) => [prediction.questionId, prediction])),
    [predictions.data],
  );

  if (questions.isPending) {
    return <Spinner label="Loading the questions…" />;
  }
  if (questions.data === undefined) {
    return (
      <div className="px-4 pb-4">
        <Problem error={questions.error} />
      </div>
    );
  }

  return (
    <div className="border-t border-line">
      {group.introMarkdown.trim().length > 0 && (
        <p className="mx-4 mt-4 rounded bg-sunk px-3.5 py-3 text-[13px] leading-relaxed text-ink-soft text-pretty">
          {group.introMarkdown}
        </p>
      )}

      <div className="flex flex-col divide-y divide-line/60">
        {questions.data.map((question) =>
          editable ? (
            <QuestionForm
              key={question.id}
              tournamentId={tournamentId}
              question={question}
              existing={byQuestion.get(question.id)?.payload ?? null}
              allPredictions={predictions.data ?? []}
              questions={questions.data}
            />
          ) : (
            <div key={question.id} className="px-4 py-3.5">
              <p className="text-sm font-semibold">{question.prompt}</p>
              <p className="mt-1 text-[13px] text-muted">
                <span className="text-faint">You said </span>
                {describePayload(byQuestion.get(question.id)?.payload ?? null, nameOf)}
              </p>
            </div>
          ),
        )}
      </div>
    </div>
  );
}
