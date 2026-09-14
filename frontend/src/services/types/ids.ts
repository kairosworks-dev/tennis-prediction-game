/**
 * Identifier aliases.
 *
 * These are plain strings at runtime. They exist so that a signature reads
 * `getTournament(id: TournamentId)` rather than `getTournament(id: string)`,
 * and so that a later move to branded types is a change in one file.
 */
export type UserId = string;
export type PlayerId = string;
export type TournamentId = string;
export type DrawId = string;
export type DrawSectionId = string;
export type DrawEntryId = string;
export type ParticipationId = string;
export type BetGroupId = string;
export type QuestionId = string;
export type PredictionId = string;
export type ScoreEntryId = string;

/** ISO 8601, UTC, e.g. `2026-05-25T09:00:00Z`. */
export type IsoDateTime = string;

/** ISO 8601 calendar date, e.g. `2026-05-25`. */
export type IsoDate = string;
