import type { ApiClient } from '../apiClient';
import { ApiError, type ProblemDetail } from '../errors';
import type {
  AuthenticatedUser, BetGroup, BetGroupId, Draw, DrawId, DrawSectionWithEntries,
  JoinTournamentRequest, LoginRequest, NextGameTeaser, Participation, Prediction,
  PutDrawOutcomesRequest, PutPredictionRequest, PutQuestionOutcomeRequest, Question,
  RankingEntry, RecalculateResult, RegisterRequest, ScoreBreakdown, TournamentDetail,
  TournamentId, TournamentSummary, User,
} from '../types';

/**
 * The real API over `fetch` (step 3 onward).
 *
 * This is the only file in the application permitted to touch the network —
 * the ESLint rule exempts `src/services/http/` and nothing else. Every method
 * maps to exactly one operation in `openapi.yaml`, and the shapes it returns
 * are the ones declared in `../types`, which the contract documents.
 *
 * Errors arrive as RFC 7807 problem details and are rethrown as `ApiError`, so
 * a component handles a failure the same way whichever client is in use.
 */
export class HttpApiClient implements ApiClient {
  constructor(private readonly baseUrl: string = '/api') {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      // The session is an HTTP-only cookie, so every call has to carry it.
      credentials: 'include',
      headers: init.body === undefined ? {} : { 'Content-Type': 'application/json' },
      ...init,
    });

    if (!response.ok) {
      throw new ApiError(await this.problemFrom(response));
    }
    if (response.status === 204 || response.headers.get('content-length') === '0') {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  /** A failing endpoint should still produce a usable message. */
  private async problemFrom(response: Response): Promise<ProblemDetail> {
    try {
      const body: unknown = await response.json();
      if (typeof body === 'object' && body !== null && 'detail' in body) {
        return body as ProblemDetail;
      }
    } catch {
      // A proxy error or a dropped connection has no JSON body.
    }
    return {
      type: 'about:blank',
      title: response.statusText || 'Request failed',
      status: response.status,
      detail: `The server answered ${response.status}.`,
    };
  }

  private post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  }

  private put<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: 'PUT', body: JSON.stringify(body) });
  }

  /* --- authentication --- */
  register(request: RegisterRequest): Promise<AuthenticatedUser> {
    return this.post<AuthenticatedUser>('/auth/register', request);
  }

  login(request: LoginRequest): Promise<AuthenticatedUser> {
    return this.post<AuthenticatedUser>('/auth/login', request);
  }

  async logout(): Promise<void> {
    await this.post<undefined>('/auth/logout');
  }

  getCurrentUser(): Promise<User | null> {
    return this.request<User | null>('/me');
  }

  /* --- landing page --- */
  getNextGame(): Promise<NextGameTeaser | null> {
    return this.request<NextGameTeaser | null>('/public/next-game');
  }

  /* --- game selection --- */
  listTournaments(): Promise<readonly TournamentSummary[]> {
    return this.request<readonly TournamentSummary[]>('/tournaments');
  }

  getTournament(tournamentId: TournamentId): Promise<TournamentDetail> {
    return this.request<TournamentDetail>(`/tournaments/${tournamentId}`);
  }

  joinTournament(request: JoinTournamentRequest): Promise<Participation> {
    return this.post<Participation>(`/tournaments/${request.tournamentId}/join`, request);
  }

  /* --- inside a game --- */
  listDraws(tournamentId: TournamentId): Promise<readonly Draw[]> {
    return this.request<readonly Draw[]>(`/tournaments/${tournamentId}/draws`);
  }

  listDrawEntries(
    tournamentId: TournamentId,
    drawId: DrawId,
  ): Promise<readonly DrawSectionWithEntries[]> {
    return this.request<readonly DrawSectionWithEntries[]>(
      `/tournaments/${tournamentId}/draws/${drawId}/entries`,
    );
  }

  listBetGroups(tournamentId: TournamentId): Promise<readonly BetGroup[]> {
    return this.request<readonly BetGroup[]>(`/tournaments/${tournamentId}/bet-groups`);
  }

  listQuestions(
    tournamentId: TournamentId,
    betGroupId: BetGroupId,
  ): Promise<readonly Question[]> {
    return this.request<readonly Question[]>(
      `/tournaments/${tournamentId}/bet-groups/${betGroupId}/questions`,
    );
  }

  listOwnPredictions(tournamentId: TournamentId): Promise<readonly Prediction[]> {
    return this.request<readonly Prediction[]>(`/tournaments/${tournamentId}/predictions`);
  }

  putPrediction(request: PutPredictionRequest): Promise<Prediction> {
    return this.put<Prediction>(
      `/tournaments/${request.tournamentId}/questions/${request.questionId}/prediction`,
      request,
    );
  }

  getScoreBreakdown(tournamentId: TournamentId): Promise<ScoreBreakdown> {
    return this.request<ScoreBreakdown>(`/tournaments/${tournamentId}/scores`);
  }

  getRanking(tournamentId: TournamentId): Promise<readonly RankingEntry[]> {
    return this.request<readonly RankingEntry[]>(`/tournaments/${tournamentId}/ranking`);
  }

  /* --- results entry --- */
  putDrawOutcomes(request: PutDrawOutcomesRequest): Promise<readonly DrawSectionWithEntries[]> {
    return this.put<readonly DrawSectionWithEntries[]>(
      `/admin/draws/${request.drawId}/outcomes`,
      request,
    );
  }

  async putQuestionOutcome(request: PutQuestionOutcomeRequest): Promise<void> {
    await this.put<undefined>(`/admin/questions/${request.questionId}/outcome`, request);
  }

  recalculateScores(tournamentId: TournamentId): Promise<RecalculateResult> {
    return this.post<RecalculateResult>(`/admin/tournaments/${tournamentId}/recalculate`);
  }
}
