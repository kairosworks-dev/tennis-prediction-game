import type {
  AuthenticatedUser, BetGroup, BetGroupId, Draw, DrawId, DrawSectionWithEntries,
  JoinTournamentRequest, LoginRequest, NextGameTeaser, Participation,
  Prediction, PutDrawOutcomesRequest, PutPredictionRequest,
  PutQuestionOutcomeRequest, Question, RankingEntry, RecalculateResult,
  RegisterRequest, ScoreBreakdown, TournamentDetail, TournamentId,
  TournamentSummary, User,
} from './types';

/**
 * The single agreement between the application and its backend.
 *
 * Every backend interaction goes through this interface (AGENTS.md hard rule
 * 1). Two implementations exist: `MockApiClient` for step 1 and
 * `HttpApiClient` from step 3, selected by environment variable. From step 2,
 * every method here maps to exactly one operation in `openapi.yaml`, so the
 * shape of this interface is the shape of the API.
 *
 * Every method declares its request and response type explicitly. No `any`,
 * no implicit return types. Failures reject with an `ApiError` carrying an
 * RFC 7807 problem detail.
 *
 * This is the first-pass surface (decision D14). The deferred operations —
 * email verification, password reset, profile editing, account deletion, the
 * post-lock comparison view, and the admin screens other than results entry —
 * are listed in spec 13.1. `MockApiClient` still implements several of them,
 * deliberately: they are working code kept for the next pass, and keeping them
 * off this interface is what stops them reaching the contract and the backend
 * before there is a screen that needs them.
 */
export interface ApiClient {
  /* --- authentication (spec 4.2) --- */
  register(request: RegisterRequest): Promise<AuthenticatedUser>;
  login(request: LoginRequest): Promise<AuthenticatedUser>;
  logout(): Promise<void>;
  /** Null when nobody is signed in. Does not throw for an anonymous visitor. */
  getCurrentUser(): Promise<User | null>;

  /* --- landing page (spec 4.1), unauthenticated --- */
  getNextGame(): Promise<NextGameTeaser | null>;

  /* --- game selection (spec 4.3) --- */
  listTournaments(): Promise<readonly TournamentSummary[]>;
  getTournament(tournamentId: TournamentId): Promise<TournamentDetail>;
  joinTournament(request: JoinTournamentRequest): Promise<Participation>;

  /* --- inside a game (spec 4.4) --- */
  listDraws(tournamentId: TournamentId): Promise<readonly Draw[]>;
  listDrawEntries(
    tournamentId: TournamentId,
    drawId: DrawId,
  ): Promise<readonly DrawSectionWithEntries[]>;
  listBetGroups(tournamentId: TournamentId): Promise<readonly BetGroup[]>;
  listQuestions(
    tournamentId: TournamentId,
    betGroupId: BetGroupId,
  ): Promise<readonly Question[]>;
  listOwnPredictions(tournamentId: TournamentId): Promise<readonly Prediction[]>;
  putPrediction(request: PutPredictionRequest): Promise<Prediction>;
  getScoreBreakdown(tournamentId: TournamentId): Promise<ScoreBreakdown>;
  getRanking(tournamentId: TournamentId): Promise<readonly RankingEntry[]>;

  /* --- results entry (spec 4.5.4). Authorisation is checked server-side. --- */
  /** The outcome grid. One save settles every typed question (decision D9). */
  putDrawOutcomes(request: PutDrawOutcomesRequest): Promise<readonly DrawSectionWithEntries[]>;
  putQuestionOutcome(request: PutQuestionOutcomeRequest): Promise<void>;
  /** Idempotent: safe to run repeatedly, rebuilds every score entry. */
  recalculateScores(tournamentId: TournamentId): Promise<RecalculateResult>;
}
