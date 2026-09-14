import { useMutation, useQuery, useQueryClient, type UseMutationResult, type UseQueryResult } from '@tanstack/react-query';
import { useApi } from './useApi';
import type {
  BetGroup, BetGroupId, Draw, DrawId, DrawSectionWithEntries,
  JoinTournamentRequest, LoginRequest, NextGameTeaser, Participation,
  Prediction, PutPredictionRequest, Question, RankingEntry, RegisterRequest,
  ScoreBreakdown, TournamentDetail, TournamentId, TournamentSummary, User,
  AuthenticatedUser,
} from '../services';

/**
 * TanStack Query wrappers over the service layer.
 *
 * Pages consume these, never `ApiClient` directly, so caching, loading and
 * error handling are decided once rather than per page. Every hook here is a
 * thin call — no rules, no derivation, nothing the backend should own.
 */

export const keys = {
  session: ['session'] as const,
  nextGame: ['next-game'] as const,
  tournaments: ['tournaments'] as const,
  tournament: (id: TournamentId) => ['tournament', id] as const,
  draws: (id: TournamentId) => ['draws', id] as const,
  drawEntries: (id: TournamentId, drawId: DrawId) => ['draw-entries', id, drawId] as const,
  betGroups: (id: TournamentId) => ['bet-groups', id] as const,
  questions: (id: TournamentId, groupId: BetGroupId) => ['questions', id, groupId] as const,
  predictions: (id: TournamentId) => ['predictions', id] as const,
  scores: (id: TournamentId) => ['scores', id] as const,
  ranking: (id: TournamentId) => ['ranking', id] as const,
};

export function useSession(): UseQueryResult<User | null> {
  const api = useApi();
  return useQuery({ queryKey: keys.session, queryFn: () => api.getCurrentUser(), staleTime: Infinity });
}

export function useNextGame(): UseQueryResult<NextGameTeaser | null> {
  const api = useApi();
  return useQuery({ queryKey: keys.nextGame, queryFn: () => api.getNextGame() });
}

export function useTournaments(): UseQueryResult<readonly TournamentSummary[]> {
  const api = useApi();
  return useQuery({ queryKey: keys.tournaments, queryFn: () => api.listTournaments() });
}

export function useTournament(id: TournamentId): UseQueryResult<TournamentDetail> {
  const api = useApi();
  return useQuery({ queryKey: keys.tournament(id), queryFn: () => api.getTournament(id) });
}

export function useDraws(id: TournamentId): UseQueryResult<readonly Draw[]> {
  const api = useApi();
  return useQuery({ queryKey: keys.draws(id), queryFn: () => api.listDraws(id) });
}

export function useDrawEntries(
  id: TournamentId,
  drawId: DrawId | undefined,
): UseQueryResult<readonly DrawSectionWithEntries[]> {
  const api = useApi();
  return useQuery({
    queryKey: keys.drawEntries(id, drawId ?? ''),
    queryFn: () => api.listDrawEntries(id, drawId ?? ''),
    enabled: drawId !== undefined,
  });
}

export function useBetGroups(id: TournamentId): UseQueryResult<readonly BetGroup[]> {
  const api = useApi();
  return useQuery({ queryKey: keys.betGroups(id), queryFn: () => api.listBetGroups(id) });
}

export function useQuestions(
  id: TournamentId,
  groupId: BetGroupId | undefined,
): UseQueryResult<readonly Question[]> {
  const api = useApi();
  return useQuery({
    queryKey: keys.questions(id, groupId ?? ''),
    queryFn: () => api.listQuestions(id, groupId ?? ''),
    enabled: groupId !== undefined,
  });
}

export function useOwnPredictions(id: TournamentId): UseQueryResult<readonly Prediction[]> {
  const api = useApi();
  return useQuery({ queryKey: keys.predictions(id), queryFn: () => api.listOwnPredictions(id) });
}

export function useScoreBreakdown(id: TournamentId): UseQueryResult<ScoreBreakdown> {
  const api = useApi();
  return useQuery({ queryKey: keys.scores(id), queryFn: () => api.getScoreBreakdown(id) });
}

export function useRanking(id: TournamentId): UseQueryResult<readonly RankingEntry[]> {
  const api = useApi();
  return useQuery({ queryKey: keys.ranking(id), queryFn: () => api.getRanking(id) });
}

export function useLogin(): UseMutationResult<AuthenticatedUser, Error, LoginRequest> {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: LoginRequest) => api.login(request),
    onSuccess: () => queryClient.invalidateQueries(),
  });
}

export function useRegister(): UseMutationResult<AuthenticatedUser, Error, RegisterRequest> {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: RegisterRequest) => api.register(request),
    onSuccess: () => queryClient.invalidateQueries(),
  });
}

export function useLogout(): UseMutationResult<void, Error, void> {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.logout(),
    onSuccess: () => {
      queryClient.clear();
    },
  });
}

export function useJoinTournament(): UseMutationResult<Participation, Error, JoinTournamentRequest> {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: JoinTournamentRequest) => api.joinTournament(request),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.tournaments }),
  });
}

export function usePutPrediction(
  tournamentId: TournamentId,
): UseMutationResult<Prediction, Error, PutPredictionRequest> {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: PutPredictionRequest) => api.putPrediction(request),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.predictions(tournamentId) });
      await queryClient.invalidateQueries({ queryKey: keys.scores(tournamentId) });
    },
  });
}
