import type {
  BetGroupId, DrawEntryId, DrawId, DrawSectionId, IsoDate, IsoDateTime,
  ParticipationId, PlayerId, QuestionId, ScoreEntryId, TournamentId, UserId,
} from './ids';
import type {
  AnswerType, BetGroupKind, BetGroupStatus, MatchFormat, ParticipationStatus,
  QuestionFamily, RoundReached, Surface, Tour, TournamentCategory,
  TournamentStatus, TournamentVisibility, TypedQuestionKind,
} from './enums';
import type { QuestionOutcomePayload } from './predictions';

/** Spec 6.1. Password hashes never cross the API boundary. */
export interface User {
  readonly id: UserId;
  readonly email: string;
  readonly displayName: string;
  readonly fullName: string | null;
  readonly isAdmin: boolean;
  readonly isActive: boolean;
  readonly emailVerifiedAt: IsoDateTime | null;
  readonly createdAt: IsoDateTime;
}

/** The global player registry (spec 6.1). */
export interface Player {
  readonly id: PlayerId;
  readonly fullName: string;
  /** ISO 3166-1 alpha-3, e.g. `ESP`. */
  readonly countryCode: string;
  readonly tour: Tour;
}

/**
 * Point values for one game, editable per tournament (decision D10). Structure
 * is fixed; values are not. Editing a profile does not retroactively rescore.
 */
export interface ScoringProfile {
  readonly quarterFinalistPoints: number;
  readonly semiFinalistPoints: number;
  readonly finalistPoints: number;
  readonly championPoints: number;
  /** Points for an underperformer exiting in round 1, 2 and 3 respectively. */
  readonly underperformerPoints: readonly [number, number, number];
  /** Points for a breakout reaching R16, QF, SF, F and winning respectively. */
  readonly breakoutPoints: readonly [number, number, number, number, number];
  readonly featuredMatchWinnerPoints: number;
  readonly featuredMatchSetScorePoints: number;
}

export interface Tournament {
  readonly id: TournamentId;
  readonly name: string;
  readonly category: TournamentCategory;
  readonly surface: Surface;
  readonly location: string;
  readonly startDate: IsoDate;
  readonly endDate: IsoDate;
  readonly signupDeadline: IsoDateTime;
  readonly visibility: TournamentVisibility;
  /** Present only for private games, and only to an admin. */
  readonly joinCode: string | null;
  readonly status: TournamentStatus;
  readonly rulesMarkdown: string;
  readonly scoringProfile: ScoringProfile;
  readonly createdAt: IsoDateTime;
}

/** First-class child of a tournament, one or two per game (decision D6). */
export interface Draw {
  readonly id: DrawId;
  readonly tournamentId: TournamentId;
  readonly tour: Tour;
  readonly drawSize: number;
  /** Sets needed to win a match: 3 for best of five, 2 for best of three. */
  readonly bestOf: MatchFormat;
  readonly officialDrawUrl: string | null;
}

/** One eighth of a draw. Each section feeds exactly one quarter-final slot. */
export interface DrawSection {
  readonly id: DrawSectionId;
  readonly drawId: DrawId;
  /** 1..8. */
  readonly index: number;
}

export interface DrawEntry {
  readonly id: DrawEntryId;
  readonly drawId: DrawId;
  readonly sectionId: DrawSectionId;
  readonly playerId: PlayerId;
  /** Null for an unseeded entrant. */
  readonly seed: number | null;
}

/** A section with its entrants resolved, which is how the UI reads a draw. */
export interface DrawSectionWithEntries {
  readonly section: DrawSection;
  readonly entries: readonly DrawEntryWithPlayer[];
}

export interface DrawEntryWithPlayer {
  readonly entry: DrawEntry;
  readonly player: Player;
  /** From the outcome grid. Null until the admin records it. */
  readonly roundReached: RoundReached | null;
}

export interface Participation {
  readonly id: ParticipationId;
  readonly userId: UserId;
  readonly tournamentId: TournamentId;
  readonly joinedAt: IsoDateTime;
  readonly status: ParticipationStatus;
}

export interface BetGroup {
  readonly id: BetGroupId;
  readonly tournamentId: TournamentId;
  readonly kind: BetGroupKind;
  /** Null for the tournament bet group. */
  readonly round: number | null;
  readonly title: string;
  readonly introMarkdown: string;
  readonly deadline: IsoDateTime;
  readonly status: BetGroupStatus;
}

export interface QuestionChoiceOption {
  readonly id: string;
  readonly label: string;
}

/**
 * Single-table inheritance (spec 6.2): `family` splits typed from generic,
 * `kind` narrows the typed case and is null for a generic question.
 */
export interface Question {
  readonly id: QuestionId;
  readonly betGroupId: BetGroupId;
  /** Null for a question that is not bound to one draw. */
  readonly drawId: DrawId | null;
  readonly family: QuestionFamily;
  readonly kind: TypedQuestionKind | null;
  readonly prompt: string;
  readonly answerType: AnswerType;
  /** Present when `answerType` is CHOICE. */
  readonly options: readonly QuestionChoiceOption[] | null;
  /**
   * Present when `answerType` is MATCH_RESULT: the two players in the tie, in
   * the order they should be shown. A prediction's winner must be one of them.
   */
  readonly matchup: readonly [PlayerId, PlayerId] | null;
  /** Points available, for display. The backend remains the authority. */
  readonly pointsHint: string;
  /** Unexposed per-question override (decision D7). Null in the MVP UI. */
  readonly deadlineOverride: IsoDateTime | null;
  readonly position: number;
}

/** One row of the outcome grid (decision D9). */
export interface OutcomeEntry {
  readonly drawId: DrawId;
  readonly playerId: PlayerId;
  readonly roundReached: RoundReached;
  readonly note: string | null;
}

export interface QuestionOutcome {
  readonly questionId: QuestionId;
  readonly correctAnswer: QuestionOutcomePayload;
  readonly settledAt: IsoDateTime;
  readonly note: string | null;
}

/** Derived data, rebuildable at any time (decision D9, AGENTS.md rule 7). */
export interface ScoreEntry {
  readonly id: ScoreEntryId;
  readonly participationId: ParticipationId;
  readonly questionId: QuestionId;
  readonly points: number;
  /** Human-readable audit line, e.g. "6 of 8 correct". */
  readonly reason: string;
  readonly calculatedAt: IsoDateTime;
}
