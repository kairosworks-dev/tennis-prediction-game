import type {
  AuthenticatedUser, BetGroup, CreateBetGroupRequest, CreateDrawRequest,
  CreatePlayerRequest, CreateQuestionRequest, CreateTournamentRequest, Draw,
  DrawId, DrawSectionWithEntries, JoinTournamentRequest, ListPlayersQuery,
  ListUsersQuery, LoginRequest, NextGameTeaser, Paginated, ParticipantPrediction,
  Participation, PasswordResetConfirmRequest, PasswordResetRequest, Player,
  Prediction, PutDrawEntriesRequest, PutDrawOutcomesRequest,
  PutPredictionRequest, PutQuestionOutcomeRequest, Question, RankingEntry,
  RecalculateResult, RegisterRequest, ScoreBreakdown, TournamentDetail,
  TournamentId, TournamentSummary, UpdateBetGroupRequest, UpdateProfileRequest,
  UpdateQuestionRequest, UpdateTournamentRequest, UpdateUserRequest, User,
  VerifyEmailRequest, BetGroupId, QuestionId,
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
 * no implicit return types.
 *
 * Failures reject with an `ApiError` carrying an RFC 7807 problem detail.
 */
export interface ApiClient {
  /* --- authentication and account (spec 4.2) --- */
  register(request: RegisterRequest): Promise<AuthenticatedUser>;
  login(request: LoginRequest): Promise<AuthenticatedUser>;
  logout(): Promise<void>;
  verifyEmail(request: VerifyEmailRequest): Promise<AuthenticatedUser>;
  requestPasswordReset(request: PasswordResetRequest): Promise<void>;
  confirmPasswordReset(request: PasswordResetConfirmRequest): Promise<void>;

  /** Null when nobody is signed in. Does not throw for an anonymous visitor. */
  getCurrentUser(): Promise<User | null>;
  updateCurrentUser(request: UpdateProfileRequest): Promise<User>;
  /** Anonymises rather than cascades, so past leaderboards stay intact. */
  deleteCurrentUser(): Promise<void>;

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

  /** The signed-in participant's own predictions for a game. */
  listOwnPredictions(tournamentId: TournamentId): Promise<readonly Prediction[]>;
  /**
   * Everyone's answers for one question. Rejects with 403 while the question's
   * bet group is still open (decision D7).
   */
  listQuestionPredictions(
    tournamentId: TournamentId,
    questionId: QuestionId,
  ): Promise<readonly ParticipantPrediction[]>;

  putPrediction(request: PutPredictionRequest): Promise<Prediction>;

  getScoreBreakdown(tournamentId: TournamentId): Promise<ScoreBreakdown>;
  getRanking(tournamentId: TournamentId): Promise<readonly RankingEntry[]>;

  /* --- admin (spec 4.5). Authorisation is checked server-side. --- */
  listUsers(query: ListUsersQuery): Promise<Paginated<User>>;
  updateUser(request: UpdateUserRequest): Promise<User>;
  triggerPasswordReset(request: PasswordResetRequest): Promise<void>;

  createTournament(request: CreateTournamentRequest): Promise<TournamentDetail>;
  updateTournament(request: UpdateTournamentRequest): Promise<TournamentDetail>;

  createDraw(request: CreateDrawRequest): Promise<Draw>;
  putDrawEntries(request: PutDrawEntriesRequest): Promise<readonly DrawSectionWithEntries[]>;

  createBetGroup(request: CreateBetGroupRequest): Promise<BetGroup>;
  updateBetGroup(request: UpdateBetGroupRequest): Promise<BetGroup>;
  createQuestion(request: CreateQuestionRequest): Promise<Question>;
  updateQuestion(request: UpdateQuestionRequest): Promise<Question>;

  /** The outcome grid. One save settles every typed question (decision D9). */
  putDrawOutcomes(request: PutDrawOutcomesRequest): Promise<readonly DrawSectionWithEntries[]>;
  putQuestionOutcome(request: PutQuestionOutcomeRequest): Promise<void>;
  /** Idempotent: safe to run repeatedly, rebuilds every score entry. */
  recalculateScores(tournamentId: TournamentId): Promise<RecalculateResult>;

  listPlayers(query: ListPlayersQuery): Promise<readonly Player[]>;
  createPlayer(request: CreatePlayerRequest): Promise<Player>;
}
