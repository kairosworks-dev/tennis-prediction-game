import type {
  PlayerId, PredictionPayload, QuestionOutcomePayload, RoundReached, ScoringProfile,
} from '../../types';
import { ROUNDS_REACHED } from '../../types';

/**
 * FIXTURE CONSTRUCTION ONLY — not application logic.
 *
 * AGENTS.md rule 2 puts scoring in the backend, and rule 5 makes it a pure
 * function there. This module exists because fixture data has to be internally
 * consistent: a scores screen showing a prediction, an outcome and a points
 * total that do not follow from each other is a worse mock than no mock.
 *
 * So this runs once, at fixture-build time, to derive the `ScoreEntry` rows
 * that a real backend would have written. Nothing in the application calls it,
 * `MockApiClient` serves its output as data, and it is deleted when the real
 * backend arrives in step 3. Do not import it from a component, a hook or a
 * page, and do not treat it as a reference implementation — spec section 5 is
 * the reference, and the backend engine is the authority.
 */

/** Position in the advancement order. `WITHDREW` never advanced. */
export function roundRank(round: RoundReached | null): number {
  if (round === null || round === 'WITHDREW') {
    return -1;
  }
  return ROUNDS_REACHED.indexOf(round);
}

const RANK_R16 = roundRank('R16');
const RANK_QF = roundRank('QF');
const RANK_SF = roundRank('SF');
const RANK_F = roundRank('F');
const RANK_CHAMPION = roundRank('CHAMPION');

function reached(outcomes: ReadonlyMap<PlayerId, RoundReached>, playerId: PlayerId, floor: number): boolean {
  return roundRank(outcomes.get(playerId) ?? null) >= floor;
}

/**
 * The deepest round anyone has reached. A question cannot settle before the
 * round it asks about has been played — scoring a champion pick as wrong while
 * the quarter-finals are still going is not a zero, it is a lie.
 */
function deepestRank(outcomes: ReadonlyMap<PlayerId, RoundReached>): number {
  let deepest = -1;
  for (const round of outcomes.values()) {
    deepest = Math.max(deepest, roundRank(round));
  }
  return deepest;
}

export interface FixtureScore {
  readonly points: number;
  readonly reason: string;
}

/**
 * Points and an audit line for one answered question, per spec 5.1 and 5.2.
 * Returns null when the question has not settled, which is what leaves a row
 * showing a dash rather than a zero.
 */
export function scorePrediction(
  prediction: PredictionPayload,
  correctAnswer: QuestionOutcomePayload | null,
  outcomes: ReadonlyMap<PlayerId, RoundReached>,
  profile: ScoringProfile,
  nameOf: (playerId: PlayerId) => string,
): FixtureScore | null {
  switch (prediction.kind) {
    case 'QF_PICKS': {
      if (deepestRank(outcomes) < RANK_QF) {
        return null;
      }
      const hits = prediction.picks.filter((p) => reached(outcomes, p.playerId, RANK_QF));
      return {
        points: hits.length * profile.quarterFinalistPoints,
        reason:
          hits.length === 0
            ? 'None of the eight reached the quarter-final.'
            : `${hits.length} of ${prediction.picks.length} correct — ${hits.map((h) => nameOf(h.playerId)).join(', ')}.`,
      };
    }
    case 'SF_PICKS': {
      if (deepestRank(outcomes) < RANK_SF) {
        return null;
      }
      const hits = prediction.playerIds.filter((pid) => reached(outcomes, pid, RANK_SF));
      return {
        points: hits.length * profile.semiFinalistPoints,
        reason: `${hits.length} of ${prediction.playerIds.length} reached the semi-final.`,
      };
    }
    case 'FINALIST_PICKS': {
      if (deepestRank(outcomes) < RANK_F) {
        return null;
      }
      const hits = prediction.playerIds.filter((pid) => reached(outcomes, pid, RANK_F));
      return {
        points: hits.length * profile.finalistPoints,
        reason: `${hits.length} of ${prediction.playerIds.length} reached the final.`,
      };
    }
    case 'CHAMPION': {
      if (deepestRank(outcomes) < RANK_CHAMPION) {
        return null;
      }
      const correct = reached(outcomes, prediction.playerId, RANK_CHAMPION);
      return {
        points: correct ? profile.championPoints : 0,
        reason: correct
          ? `${nameOf(prediction.playerId)} won the title.`
          : `${nameOf(prediction.playerId)} did not win the title.`,
      };
    }
    case 'UNDERPERFORMER': {
      const round = outcomes.get(prediction.playerId) ?? null;
      const exitIndex: 0 | 1 | 2 | null =
        round === 'R128' ? 0 : round === 'R64' ? 1 : round === 'R32' ? 2 : null;
      return {
        points: exitIndex === null ? 0 : profile.underperformerPoints[exitIndex],
        reason:
          exitIndex === null
            ? `${nameOf(prediction.playerId)} survived the first three rounds.`
            : `${nameOf(prediction.playerId)} exited in round ${String(exitIndex + 1)}.`,
      };
    }
    case 'BREAKOUT': {
      if (deepestRank(outcomes) < RANK_R16) {
        return null;
      }
      const rank = roundRank(outcomes.get(prediction.playerId) ?? null);
      const ladder: readonly (readonly [number, 0 | 1 | 2 | 3 | 4])[] = [
        [RANK_CHAMPION, 4], [RANK_F, 3], [RANK_SF, 2], [RANK_QF, 1], [RANK_R16, 0],
      ];
      const step = ladder.find(([floor]) => rank >= floor);
      const points = step === undefined ? 0 : profile.breakoutPoints[step[1]];
      return {
        points,
        reason:
          step === undefined
            ? `${nameOf(prediction.playerId)} did not reach the fourth round.`
            : `${nameOf(prediction.playerId)} reached ${String(outcomes.get(prediction.playerId))}.`,
      };
    }
    case 'GENERIC_MATCH_RESULT': {
      if (correctAnswer === null || correctAnswer.kind !== 'GENERIC_MATCH_RESULT') {
        return null;
      }
      const winnerCorrect = prediction.winnerId === correctAnswer.winnerId;
      // The set-score point only counts when the winner is also right (spec 5.2).
      const scoreCorrect = winnerCorrect && prediction.setScore === correctAnswer.setScore;
      const points =
        (winnerCorrect ? profile.featuredMatchWinnerPoints : 0) +
        (scoreCorrect ? profile.featuredMatchSetScorePoints : 0);
      return {
        points,
        reason: !winnerCorrect
          ? 'Wrong winner. No points.'
          : scoreCorrect
            ? 'Winner correct, set score correct.'
            : 'Winner correct, set score wrong.',
      };
    }
    case 'GENERIC_INTEGER': {
      if (correctAnswer === null || correctAnswer.kind !== 'GENERIC_INTEGER') {
        return null;
      }
      const correct = prediction.value === correctAnswer.value;
      return {
        points: correct ? 2 : 0,
        reason: correct
          ? `You said ${String(prediction.value)}. Correct.`
          : `You said ${String(prediction.value)}, it was ${String(correctAnswer.value)}.`,
      };
    }
    case 'GENERIC_CHOICE': {
      if (correctAnswer === null || correctAnswer.kind !== 'GENERIC_CHOICE') {
        return null;
      }
      const correct = prediction.optionId === correctAnswer.optionId;
      return { points: correct ? 2 : 0, reason: correct ? 'Correct.' : 'Not this time.' };
    }
    case 'GENERIC_PLAYER': {
      if (correctAnswer === null || correctAnswer.kind !== 'GENERIC_PLAYER') {
        return null;
      }
      const correct = prediction.playerId === correctAnswer.playerId;
      return {
        points: correct ? 2 : 0,
        reason: correct ? `${nameOf(prediction.playerId)}. Correct.` : `It was ${nameOf(correctAnswer.playerId)}.`,
      };
    }
  }
}
