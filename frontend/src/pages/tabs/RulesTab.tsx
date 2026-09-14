import type { ReactNode } from 'react';
import type { TournamentDetail } from '../../services';
import { categoryLabel, formatDateRange } from '../../components/format';

/** Spec 4.4.1 — tournament facts and the scoring table, rendered from the profile. */
export function RulesTab({ detail }: { detail: TournamentDetail }): ReactNode {
  const { tournament, draws } = detail;
  const p = tournament.scoringProfile;

  const facts: readonly [string, string][] = [
    ['Category', categoryLabel(tournament.category)],
    ['Surface', tournament.surface.replace('_', ' ').toLowerCase()],
    ['Location', tournament.location],
    ['Dates', formatDateRange(tournament.startDate, tournament.endDate)],
    ...draws.map(
      (draw): [string, string] => [
        `${draw.tour} draw`,
        `${draw.drawSize} · best of ${draw.bestOf === 5 ? 'five' : 'three'}`,
      ],
    ),
  ];

  const tournamentBets: readonly [string, string, string][] = [
    ['Quarter-finalists', 'One per section, eight in total', `${p.quarterFinalistPoints} ea.`],
    ['Semi-finalists', 'Four, from your quarter-finalists', `${p.semiFinalistPoints} ea.`],
    ['Finalists', 'Two, from your semi-finalists', `${p.finalistPoints} ea.`],
    ['Champion', 'One of your two finalists', `${p.championPoints}`],
    ['Underperformer', 'Seeded ten or better · exit in R1 / R2 / R3', p.underperformerPoints.join(' / ')],
    ['Breakout', 'Unseeded · R16 / QF / SF / F / title', p.breakoutPoints.join(' / ')],
  ];

  return (
    <div className="px-5 pt-5">
      <dl className="overflow-hidden rounded border border-line bg-card">
        {facts.map(([label, value]) => (
          <div key={label} className="flex gap-2.5 border-b border-line/60 px-4 py-3 last:border-0">
            <dt className="w-24 shrink-0 text-[13px] text-faint">{label}</dt>
            <dd className="grow text-[13px] font-medium capitalize">{value}</dd>
          </div>
        ))}
      </dl>

      <h2 className="pt-7 font-display text-2xl">Tournament bets</h2>
      <p className="mt-1 text-[13px] text-muted">Submitted once per draw, before play begins.</p>
      <ul className="mt-3.5 overflow-hidden rounded border border-line bg-card">
        {tournamentBets.map(([title, detailText, points]) => (
          <li key={title} className="flex items-center gap-2.5 border-b border-line/60 px-4 py-3 last:border-0">
            <div className="grow">
              <p className="text-sm font-semibold">{title}</p>
              <p className="mt-0.5 text-xs text-faint">{detailText}</p>
            </div>
            <span className="font-mono text-sm font-semibold text-court">{points}</span>
          </li>
        ))}
      </ul>

      <h2 className="pt-7 font-display text-2xl">Round bets</h2>
      <ul className="mt-3.5 overflow-hidden rounded border border-line bg-card">
        <li className="flex items-center gap-2.5 px-4 py-3">
          <div className="grow">
            <p className="text-sm font-semibold">Featured match</p>
            <p className="mt-0.5 text-xs text-faint">Winner, plus the exact set score</p>
          </div>
          <span className="font-mono text-sm font-semibold text-court">
            {p.featuredMatchWinnerPoints} + {p.featuredMatchSetScorePoints}
          </span>
        </li>
      </ul>
      <p className="mt-2.5 text-xs leading-relaxed text-faint text-pretty">
        The set-score point only counts if you also called the winner. Round bets do not have to agree
        with your bracket — contradict yourself freely.
      </p>

      {tournament.rulesMarkdown.trim().length > 0 && (
        <>
          <h2 className="pt-7 font-display text-2xl">House rules</h2>
          <div className="mt-3 rounded border border-line bg-card p-4 text-sm leading-relaxed whitespace-pre-line text-ink-soft text-pretty">
            {tournament.rulesMarkdown}
          </div>
        </>
      )}
    </div>
  );
}
