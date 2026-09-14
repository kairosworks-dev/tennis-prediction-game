import type { ReactNode } from 'react';
import { Link, NavLink, Navigate, Route, Routes, useParams } from 'react-router-dom';
import { useSession, useTournament } from '../hooks/queries';
import { Problem, Spinner } from '../components/ui';
import { categoryLabel } from '../components/format';
import { RulesTab } from './tabs/RulesTab';
import { BetsTab } from './tabs/BetsTab';
import { ScoresTab } from './tabs/ScoresTab';
import { RankingTab } from './tabs/RankingTab';

const TABS: readonly { to: string; label: string }[] = [
  { to: 'rules', label: 'Rules' },
  { to: 'bets', label: 'Bets' },
  { to: 'scores', label: 'Scores' },
  { to: 'ranking', label: 'Ranking' },
];

/** Spec 4.4 — the tab bar scoped to one game. */
export function GamePage(): ReactNode {
  const { tournamentId = '' } = useParams();
  const session = useSession();
  const detail = useTournament(tournamentId);

  if (detail.isPending) {
    return <Spinner label="Loading the game…" />;
  }
  if (detail.isError) {
    return (
      <div className="phone-shell px-5 pt-8">
        <Problem error={detail.error} />
        <Link to="/games" className="mt-4 inline-block text-sm font-semibold text-clay">
          Back to your games
        </Link>
      </div>
    );
  }

  const { tournament } = detail.data;

  return (
    <div className="phone-shell pb-12">
      <header className="bg-court">
        <div className="flex items-center gap-3 px-5 pt-4">
          <Link to="/games" aria-label="Back to your games" className="shrink-0 p-1">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="#94b0a2" strokeWidth="1.8">
              <path d="M14.5 5.5L8 12l6.5 6.5" />
            </svg>
          </Link>
          <div className="grow">
            <p className="text-[10px] font-semibold tracking-[0.12em] uppercase text-court-pale">
              {categoryLabel(tournament.category)} · {tournament.status.toLowerCase()}
            </p>
            <h1 className="font-display text-xl leading-tight text-paper">{tournament.name}</h1>
          </div>
          {session.data?.isAdmin === true && (
            <Link
              to={`/admin/${tournamentId}/results`}
              className="shrink-0 rounded border border-court-light px-2.5 py-1.5 text-[11px] font-semibold text-court-pale"
            >
              Results
            </Link>
          )}
        </div>

        <nav className="mt-3 flex px-2">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                `grow py-3.5 text-center text-xs font-medium ${
                  isActive ? 'border-b-2 border-clay font-semibold text-paper' : 'text-court-pale'
                }`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <Routes>
        <Route index element={<Navigate to="bets" replace />} />
        <Route path="rules" element={<RulesTab detail={detail.data} />} />
        <Route path="bets" element={<BetsTab tournamentId={tournamentId} />} />
        <Route path="scores" element={<ScoresTab tournamentId={tournamentId} />} />
        <Route path="ranking" element={<RankingTab tournamentId={tournamentId} />} />
      </Routes>
    </div>
  );
}
