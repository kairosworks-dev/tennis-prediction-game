/**
 * Enumerations from spec section 6.3.
 *
 * Each is a frozen array plus a union type derived from it: the array drives
 * select options and fixture generation, the union drives the type system.
 */

export const TOURNAMENT_CATEGORIES = ['GRAND_SLAM', 'ATP', 'WTA'] as const;
export type TournamentCategory = (typeof TOURNAMENT_CATEGORIES)[number];

export const TOURS = ['ATP', 'WTA'] as const;
export type Tour = (typeof TOURS)[number];

export const SURFACES = ['HARD', 'CLAY', 'GRASS', 'INDOOR_HARD'] as const;
export type Surface = (typeof SURFACES)[number];

/**
 * How far a player got. Ordered from earliest exit to the title, so a later
 * index means a deeper run. `WITHDREW` sits outside the order and is listed
 * last by convention.
 */
export const ROUNDS_REACHED = ['R128', 'R64', 'R32', 'R16', 'QF', 'SF', 'F', 'CHAMPION', 'WITHDREW'] as const;
export type RoundReached = (typeof ROUNDS_REACHED)[number];

export const TOURNAMENT_STATUSES = ['DRAFT', 'PUBLISHED', 'RUNNING', 'FINISHED'] as const;
export type TournamentStatus = (typeof TOURNAMENT_STATUSES)[number];

export const TOURNAMENT_VISIBILITIES = ['PUBLIC', 'PRIVATE'] as const;
export type TournamentVisibility = (typeof TOURNAMENT_VISIBILITIES)[number];

export const BET_GROUP_KINDS = ['TOURNAMENT', 'ROUND'] as const;
export type BetGroupKind = (typeof BET_GROUP_KINDS)[number];

export const BET_GROUP_STATUSES = ['DRAFT', 'OPEN', 'LOCKED', 'SETTLED'] as const;
export type BetGroupStatus = (typeof BET_GROUP_STATUSES)[number];

export const QUESTION_FAMILIES = ['TYPED', 'GENERIC'] as const;
export type QuestionFamily = (typeof QUESTION_FAMILIES)[number];

/** Narrows the typed case. Null for a generic question (spec 6.2). */
export const TYPED_QUESTION_KINDS = [
  'QF_PICKS',
  'SF_PICKS',
  'FINALIST_PICKS',
  'CHAMPION',
  'UNDERPERFORMER',
  'BREAKOUT',
] as const;
export type TypedQuestionKind = (typeof TYPED_QUESTION_KINDS)[number];

export const ANSWER_TYPES = ['PLAYER', 'MATCH_RESULT', 'INTEGER', 'CHOICE'] as const;
export type AnswerType = (typeof ANSWER_TYPES)[number];

export const PARTICIPATION_STATUSES = ['ACTIVE', 'WITHDRAWN'] as const;
export type ParticipationStatus = (typeof PARTICIPATION_STATUSES)[number];

/** Best-of-three and best-of-five, as the number of sets needed to win. */
export const MATCH_FORMATS = [3, 5] as const;
export type MatchFormat = (typeof MATCH_FORMATS)[number];

/**
 * Legal set scores per match format (spec 5.3). A set score outside the list
 * for its draw is rejected by the API and blocked in the UI.
 */
export const SET_SCORES_BEST_OF_THREE = ['2-0', '2-1'] as const;
export const SET_SCORES_BEST_OF_FIVE = ['3-0', '3-1', '3-2'] as const;

export type BestOfThreeSetScore = (typeof SET_SCORES_BEST_OF_THREE)[number];
export type BestOfFiveSetScore = (typeof SET_SCORES_BEST_OF_FIVE)[number];
export type SetScore = BestOfThreeSetScore | BestOfFiveSetScore;

export function legalSetScores(format: MatchFormat): readonly SetScore[] {
  return format === 3 ? SET_SCORES_BEST_OF_THREE : SET_SCORES_BEST_OF_FIVE;
}
