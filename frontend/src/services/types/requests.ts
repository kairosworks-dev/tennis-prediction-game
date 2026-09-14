import type {
  BetGroupId, DrawId, IsoDate, IsoDateTime, ParticipationId, PlayerId,
  QuestionId, TournamentId, UserId,
} from './ids';
import type {
  AnswerType, MatchFormat, RoundReached, Surface, Tour, TournamentCategory,
  TournamentVisibility, TypedQuestionKind,
} from './enums';
import type {
  BetGroup, Draw, Player, Question, QuestionChoiceOption, ScoringProfile,
  Tournament, User,
} from './entities';
import type { PredictionPayload, QuestionOutcomePayload } from './predictions';

/* -------------------------------------------------------------------------
 * Authentication and account
 * ---------------------------------------------------------------------- */

export interface RegisterRequest {
  readonly email: string;
  readonly password: string;
  readonly displayName: string;
}

export interface LoginRequest {
  readonly email: string;
  readonly password: string;
}

export interface VerifyEmailRequest {
  readonly token: string;
}

export interface PasswordResetRequest {
  readonly email: string;
}

export interface PasswordResetConfirmRequest {
  readonly token: string;
  readonly password: string;
}

export interface UpdateProfileRequest {
  readonly displayName?: string;
  readonly fullName?: string | null;
  readonly email?: string;
}

/**
 * Registration leaves the account unverified: `emailVerifiedAt` is null until
 * the token is used, and joining a game is blocked until then (spec 4.2).
 */
export interface AuthenticatedUser {
  readonly user: User;
  readonly requiresEmailVerification: boolean;
}

/* -------------------------------------------------------------------------
 * Landing page
 * ---------------------------------------------------------------------- */

/**
 * The one live block on an otherwise static landing page (decision D13). Null
 * when no game is open, which the page renders as a neutral empty state.
 */
export interface NextGameTeaser {
  readonly tournamentId: TournamentId;
  readonly name: string;
  readonly category: TournamentCategory;
  readonly surface: Surface;
  readonly location: string;
  readonly startDate: IsoDate;
  readonly endDate: IsoDate;
  readonly signupDeadline: IsoDateTime;
  readonly participantCount: number;
}

/* -------------------------------------------------------------------------
 * Game selection
 * ---------------------------------------------------------------------- */

/** The three groups the game list renders (spec 4.3). */
export type GameListState = 'OPEN_FOR_SIGNUP' | 'RUNNING' | 'FINISHED';

export interface TournamentSummary {
  readonly tournament: Tournament;
  readonly state: GameListState;
  readonly participantCount: number;
  /** Null when the signed-in user has not joined. */
  readonly participationId: ParticipationId | null;
  /** The deadline the card should count down to. Null when nothing is open. */
  readonly nextDeadline: IsoDateTime | null;
  /** Shown on a running or finished game the user is in. */
  readonly userPosition: number | null;
  readonly userPoints: number | null;
  /** Current round in play, for a running game. */
  readonly currentRound: number | null;
}

export interface TournamentDetail {
  readonly tournament: Tournament;
  readonly draws: readonly Draw[];
  readonly participantCount: number;
  readonly participationId: ParticipationId | null;
}

export interface JoinTournamentRequest {
  readonly tournamentId: TournamentId;
  /** Required for a private game (decision D4). */
  readonly joinCode?: string;
}

/* -------------------------------------------------------------------------
 * Predictions, scores, ranking
 * ---------------------------------------------------------------------- */

export interface PutPredictionRequest {
  readonly tournamentId: TournamentId;
  readonly questionId: QuestionId;
  readonly payload: PredictionPayload;
  /** A draft saves without running the completeness check (spec 4.4.2). */
  readonly asDraft: boolean;
}

/**
 * One participant's answer to one question, as the comparison view renders it.
 * Only returned for other participants once the group has locked (D7).
 */
export interface ParticipantPrediction {
  readonly participationId: ParticipationId;
  readonly displayName: string;
  readonly payload: PredictionPayload | null;
}

export interface QuestionScoreRow {
  readonly question: Question;
  readonly ownPayload: PredictionPayload | null;
  /** Null until the question settles. */
  readonly correctAnswer: QuestionOutcomePayload | null;
  readonly points: number | null;
  readonly reason: string | null;
}

export interface BetGroupScoreBlock {
  readonly betGroup: BetGroup;
  readonly rows: readonly QuestionScoreRow[];
  readonly subtotal: number;
  /** Whether other participants' answers may be shown for this group. */
  readonly comparisonAvailable: boolean;
}

export interface ScoreBreakdown {
  readonly tournamentId: TournamentId;
  readonly total: number;
  readonly position: number | null;
  readonly participantCount: number;
  readonly groups: readonly BetGroupScoreBlock[];
}

export interface RankingEntry {
  /** Ties share a position and the next position skips (decision D13). */
  readonly position: number;
  readonly participationId: ParticipationId;
  readonly displayName: string;
  readonly isCurrentUser: boolean;
  readonly totalPoints: number;
  /** Points from the most recent settled group. */
  readonly lastGroupPoints: number;
  /** Positions gained since the previous settled group. Null on the first. */
  readonly movement: number | null;
  readonly perGroupPoints: readonly BetGroupPoints[];
}

export interface BetGroupPoints {
  readonly betGroupId: BetGroupId;
  readonly title: string;
  readonly points: number;
}

/* -------------------------------------------------------------------------
 * Admin
 * ---------------------------------------------------------------------- */

export interface ListUsersQuery {
  readonly search?: string;
  readonly offset?: number;
  readonly limit?: number;
}

export interface Paginated<T> {
  readonly items: readonly T[];
  readonly total: number;
  readonly offset: number;
  readonly limit: number;
}

export interface UpdateUserRequest {
  readonly userId: UserId;
  readonly isAdmin?: boolean;
  readonly isActive?: boolean;
}

export interface CreateTournamentRequest {
  readonly name: string;
  readonly category: TournamentCategory;
  readonly surface: Surface;
  readonly location: string;
  readonly startDate: IsoDate;
  readonly endDate: IsoDate;
  readonly signupDeadline: IsoDateTime;
  readonly visibility: TournamentVisibility;
  readonly rulesMarkdown: string;
  readonly scoringProfile: ScoringProfile;
}

export type UpdateTournamentRequest = Partial<CreateTournamentRequest> & {
  readonly tournamentId: TournamentId;
  readonly status?: Tournament['status'];
};

export interface CreateDrawRequest {
  readonly tournamentId: TournamentId;
  readonly tour: Tour;
  readonly drawSize: number;
  readonly bestOf: MatchFormat;
  readonly officialDrawUrl: string | null;
}

export interface DrawEntryInput {
  readonly playerId: PlayerId;
  /** 1..8. */
  readonly sectionIndex: number;
  readonly seed: number | null;
}

/** Replaces the whole entrant list for a draw (spec 8, `PUT`). */
export interface PutDrawEntriesRequest {
  readonly drawId: DrawId;
  readonly entries: readonly DrawEntryInput[];
}

export interface CreateBetGroupRequest {
  readonly tournamentId: TournamentId;
  readonly kind: BetGroup['kind'];
  readonly round: number | null;
  readonly title: string;
  readonly introMarkdown: string;
  readonly deadline: IsoDateTime;
}

export type UpdateBetGroupRequest = Partial<Omit<CreateBetGroupRequest, 'tournamentId'>> & {
  readonly betGroupId: BetGroupId;
  readonly status?: BetGroup['status'];
};

export interface CreateQuestionRequest {
  readonly betGroupId: BetGroupId;
  readonly drawId: DrawId | null;
  readonly family: Question['family'];
  readonly kind: TypedQuestionKind | null;
  readonly prompt: string;
  readonly answerType: AnswerType;
  readonly options: readonly QuestionChoiceOption[] | null;
  readonly matchup: readonly [PlayerId, PlayerId] | null;
  readonly pointsHint: string;
  readonly position: number;
}

export type UpdateQuestionRequest = Partial<Omit<CreateQuestionRequest, 'betGroupId'>> & {
  readonly questionId: QuestionId;
};

export interface OutcomeEntryInput {
  readonly playerId: PlayerId;
  readonly roundReached: RoundReached;
  readonly note: string | null;
}

/** The single grid that settles every typed question (decision D9). */
export interface PutDrawOutcomesRequest {
  readonly drawId: DrawId;
  readonly entries: readonly OutcomeEntryInput[];
}

export interface PutQuestionOutcomeRequest {
  readonly questionId: QuestionId;
  readonly correctAnswer: QuestionOutcomePayload;
  readonly note: string | null;
}

export interface RecalculateResult {
  readonly tournamentId: TournamentId;
  readonly scoreEntriesWritten: number;
  readonly calculatedAt: IsoDateTime;
}

export interface CreatePlayerRequest {
  readonly fullName: string;
  readonly countryCode: string;
  readonly tour: Tour;
}

export interface ListPlayersQuery {
  readonly search?: string;
  readonly tour?: Tour;
}

export type { Player };
