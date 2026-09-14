import type { ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useSession } from './hooks/queries';
import { Spinner } from './components/ui';
import { LandingPage } from './pages/LandingPage';
import { SignInPage } from './pages/SignInPage';
import { SignUpPage } from './pages/SignUpPage';
import { GamesPage } from './pages/GamesPage';
import { GamePage } from './pages/GamePage';
import { ResultsPage } from './pages/ResultsPage';

/**
 * The frontend hides a route it believes the user cannot use. It is never the
 * authority — every admin call is checked server-side (AGENTS.md hard rule 2),
 * and a participant who navigates to /admin by hand gets a 403 from the API,
 * not a blank screen.
 */
function RequireSession({ admin = false, children }: { admin?: boolean; children: ReactNode }): ReactNode {
  const session = useSession();
  const location = useLocation();

  if (session.isPending) {
    return <Spinner label="Checking your session…" />;
  }
  if (session.data === null || session.data === undefined) {
    return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />;
  }
  if (admin && !session.data.isAdmin) {
    return <Navigate to="/games" replace />;
  }
  return children;
}

export function App(): ReactNode {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/sign-in" element={<SignInPage />} />
      <Route path="/sign-up" element={<SignUpPage />} />
      <Route
        path="/games"
        element={
          <RequireSession>
            <GamesPage />
          </RequireSession>
        }
      />
      <Route
        path="/games/:tournamentId/*"
        element={
          <RequireSession>
            <GamePage />
          </RequireSession>
        }
      />
      <Route
        path="/admin/:tournamentId/results"
        element={
          <RequireSession admin>
            <ResultsPage />
          </RequireSession>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
