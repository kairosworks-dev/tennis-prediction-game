import type { PlayerId, PredictionId, ParticipationId, QuestionId, IsoDateTime } from './ids';
import type { SetScore } from './enums';

/**
 * Prediction payloads, as a discriminated union keyed on question kind
 * (AGENTS.md frontend conventions). Do not widen this to a permissive record
 * type: the discriminant is what lets a form, a scoring reason and an API
 * schema all agree on the shape of one answer.
 *
 * The six TYPED kinds mirror spec 5.1. The four GENERIC_* kinds mirror the
 * generic answer types from spec 4.5.3, one per `AnswerType`.
 */

/** One quarter-finalist pick, bound to the section it came from. */
export interface SectionPick {
  /** 1..8 — the section this pick answers for. */
  readonly sectionIndex: number;
  readonly playerId: PlayerId;
}

/** Exactly one player per section, eight in total (spec 5.3). */
export interface QuarterFinalPicksPayload {
  readonly kind: 'QF_PICKS';
  readonly picks: readonly SectionPick[];
}

/** Four, each drawn from the quarter-final picks (spec 5.3). */
export interface SemiFinalPicksPayload {
  readonly kind: 'SF_PICKS';
  readonly playerIds: readonly PlayerId[];
}

/** Two, each drawn from the semi-final picks (spec 5.3). */
export interface FinalistPicksPayload {
  readonly kind: 'FINALIST_PICKS';
  readonly playerIds: readonly PlayerId[];
}

/** One of the finalist picks (spec 5.3). */
export interface ChampionPayload {
  readonly kind: 'CHAMPION';
  readonly playerId: PlayerId;
}

/** An entrant seeded 10 or better (spec 5.3). */
export interface UnderperformerPayload {
  readonly kind: 'UNDERPERFORMER';
  readonly playerId: PlayerId;
}

/** An unseeded entrant (spec 5.3). */
export interface BreakoutPayload {
  readonly kind: 'BREAKOUT';
  readonly playerId: PlayerId;
}

/** Generic question, answer type PLAYER. */
export interface GenericPlayerPayload {
  readonly kind: 'GENERIC_PLAYER';
  readonly playerId: PlayerId;
}

/**
 * Generic question, answer type MATCH_RESULT. The set score must be legal for
 * the draw's match format; the set-score point is only awarded when the winner
 * is also correct (spec 5.2).
 */
export interface GenericMatchResultPayload {
  readonly kind: 'GENERIC_MATCH_RESULT';
  readonly winnerId: PlayerId;
  readonly setScore: SetScore;
}

/** Generic question, answer type INTEGER. */
export interface GenericIntegerPayload {
  readonly kind: 'GENERIC_INTEGER';
  readonly value: number;
}

/** Generic question, answer type CHOICE. `optionId` indexes `Question.options`. */
export interface GenericChoicePayload {
  readonly kind: 'GENERIC_CHOICE';
  readonly optionId: string;
}

export type PredictionPayload =
  | QuarterFinalPicksPayload
  | SemiFinalPicksPayload
  | FinalistPicksPayload
  | ChampionPayload
  | UnderperformerPayload
  | BreakoutPayload
  | GenericPlayerPayload
  | GenericMatchResultPayload
  | GenericIntegerPayload
  | GenericChoicePayload;

export type PredictionPayloadKind = PredictionPayload['kind'];

/**
 * A settled answer takes the same shape as the prediction it is compared
 * against, which is what keeps scoring a pure comparison.
 */
export type QuestionOutcomePayload = PredictionPayload;

export interface Prediction {
  readonly id: PredictionId;
  readonly participationId: ParticipationId;
  readonly questionId: QuestionId;
  readonly payload: PredictionPayload;
  readonly submittedAt: IsoDateTime | null;
  readonly updatedAt: IsoDateTime;
}
