import type {
  Draw, DrawEntry, PlayerId, PredictionPayload, Question, QuestionId, TypedQuestionKind,
} from '../types';
import { legalSetScores } from '../types';
import { validationFailed } from '../errors';

/**
 * The validation rules from spec section 5.3.
 *
 * These run here because `MockApiClient` stands in for the backend, and the
 * backend is where rule enforcement lives (AGENTS.md rule 2). Forms get their
 * own Zod schemas for user experience; those mirror these rules and are never
 * the authority. When the two disagree, this side wins — and from step 3, the
 * real API wins over both.
 */

export interface ValidationContext {
  readonly question: Question;
  readonly draw: Draw | null;
  /** Entrants of the question's draw. Empty for a question without one. */
  readonly entries: readonly DrawEntry[];
  /** The participant's other answers in the same bet group and draw. */
  readonly siblingPayloads: ReadonlyMap<TypedQuestionKind, PredictionPayload>;
  readonly questionsInGroup: readonly Question[];
  /** Ids of the questions that must already be answered, by kind. */
  readonly questionIdByKind: ReadonlyMap<TypedQuestionKind, QuestionId>;
}

const UNDERPERFORMER_MAX_SEED = 10;
const SECTION_COUNT = 8;

function playerIdsOf(payload: PredictionPayload | undefined): readonly PlayerId[] {
  if (payload === undefined) {
    return [];
  }
  switch (payload.kind) {
    case 'QF_PICKS':
      return payload.picks.map((p) => p.playerId);
    case 'SF_PICKS':
    case 'FINALIST_PICKS':
      return payload.playerIds;
    case 'CHAMPION':
      return [payload.playerId];
    default:
      return [];
  }
}

function requireSubsetOf(
  chosen: readonly PlayerId[],
  pool: readonly PlayerId[],
  expectedSize: number,
  label: string,
  poolLabel: string,
): void {
  if (chosen.length !== expectedSize) {
    throw validationFailed(`Choose exactly ${String(expectedSize)} ${label}.`, {
      payload: [`Expected ${String(expectedSize)}, got ${String(chosen.length)}.`],
    });
  }
  if (new Set(chosen).size !== chosen.length) {
    throw validationFailed(`The same player appears twice in your ${label}.`, {
      payload: ['Each pick must be a different player.'],
    });
  }
  if (pool.length === 0) {
    throw validationFailed(`Answer the ${poolLabel} question first.`, {
      payload: [`Your ${label} are drawn from your ${poolLabel}.`],
    });
  }
  const allowed = new Set(pool);
  const stray = chosen.filter((pid) => !allowed.has(pid));
  if (stray.length > 0) {
    throw validationFailed(`Your ${label} must come from your ${poolLabel}.`, {
      payload: [`${String(stray.length)} pick(s) are not among your ${poolLabel}.`],
    });
  }
}

/** Throws an `ApiError` carrying an RFC 7807 problem when the answer is illegal. */
export function validatePrediction(payload: PredictionPayload, context: ValidationContext): void {
  const { question, draw, entries, siblingPayloads } = context;
  const seedOf = new Map(entries.map((e) => [e.playerId, e.seed] as const));
  const sectionOf = new Map(entries.map((e) => [e.playerId, e.sectionId] as const));

  const requireEntrant = (playerId: PlayerId): void => {
    if (!sectionOf.has(playerId)) {
      throw validationFailed('That player is not in this draw.', {
        payload: ['Pick an entrant of the draw this question belongs to.'],
      });
    }
  };

  switch (payload.kind) {
    case 'QF_PICKS': {
      if (payload.picks.length !== SECTION_COUNT) {
        throw validationFailed(`Choose one player from each of the ${String(SECTION_COUNT)} sections.`, {
          payload: [`${String(payload.picks.length)} of ${String(SECTION_COUNT)} sections answered.`],
        });
      }
      const seen = new Set<number>();
      for (const pick of payload.picks) {
        if (pick.sectionIndex < 1 || pick.sectionIndex > SECTION_COUNT) {
          throw validationFailed(`Section ${String(pick.sectionIndex)} does not exist.`);
        }
        if (seen.has(pick.sectionIndex)) {
          throw validationFailed(`Section ${String(pick.sectionIndex)} has two picks.`, {
            payload: ['Exactly one player per section.'],
          });
        }
        seen.add(pick.sectionIndex);
        requireEntrant(pick.playerId);

        const sectionId = sectionOf.get(pick.playerId);
        const expected = entries.find((e) => e.playerId === pick.playerId)?.sectionId;
        if (sectionId !== expected) {
          throw validationFailed('That player is not in the section you picked them for.');
        }
      }
      if (new Set(payload.picks.map((p) => p.playerId)).size !== payload.picks.length) {
        throw validationFailed('The same player cannot fill two sections.');
      }
      return;
    }

    case 'SF_PICKS':
      requireSubsetOf(
        payload.playerIds,
        playerIdsOf(siblingPayloads.get('QF_PICKS')),
        4,
        'semi-finalists',
        'quarter-finalists',
      );
      return;

    case 'FINALIST_PICKS':
      requireSubsetOf(
        payload.playerIds,
        playerIdsOf(siblingPayloads.get('SF_PICKS')),
        2,
        'finalists',
        'semi-finalists',
      );
      return;

    case 'CHAMPION':
      requireSubsetOf(
        [payload.playerId],
        playerIdsOf(siblingPayloads.get('FINALIST_PICKS')),
        1,
        'champion',
        'finalists',
      );
      return;

    case 'UNDERPERFORMER': {
      requireEntrant(payload.playerId);
      const seed = seedOf.get(payload.playerId) ?? null;
      if (seed === null || seed > UNDERPERFORMER_MAX_SEED) {
        throw validationFailed(
          `The underperformer must be seeded ${String(UNDERPERFORMER_MAX_SEED)} or better.`,
          { payload: [seed === null ? 'That player is unseeded.' : `That player is seeded ${String(seed)}.`] },
        );
      }
      return;
    }

    case 'BREAKOUT': {
      requireEntrant(payload.playerId);
      const seed = seedOf.get(payload.playerId) ?? null;
      if (seed !== null) {
        throw validationFailed('The breakout pick must be an unseeded entrant.', {
          payload: [`That player is seeded ${String(seed)}.`],
        });
      }
      return;
    }

    case 'GENERIC_MATCH_RESULT': {
      if (question.matchup === null) {
        throw validationFailed('This question has no match attached to it.');
      }
      if (!question.matchup.includes(payload.winnerId)) {
        throw validationFailed('The winner must be one of the two players in the tie.');
      }
      const format = draw?.bestOf ?? 3;
      const legal = legalSetScores(format);
      if (!legal.includes(payload.setScore)) {
        throw validationFailed(
          `${payload.setScore} is not a legal result in a best-of-${format === 3 ? 'three' : 'five'} match.`,
          { payload: [`Legal scores: ${legal.join(', ')}.`] },
        );
      }
      return;
    }

    case 'GENERIC_INTEGER': {
      if (!Number.isInteger(payload.value) || payload.value < 0) {
        throw validationFailed('Answer with a whole number of zero or more.');
      }
      return;
    }

    case 'GENERIC_CHOICE': {
      const options = question.options ?? [];
      if (!options.some((o) => o.id === payload.optionId)) {
        throw validationFailed('That is not one of the offered answers.');
      }
      return;
    }

    case 'GENERIC_PLAYER': {
      requireEntrant(payload.playerId);
      return;
    }
  }
}

/** The payload kind a question expects, so a mismatched shape is caught early. */
export function expectedPayloadKind(question: Question): PredictionPayload['kind'] {
  if (question.family === 'TYPED' && question.kind !== null) {
    return question.kind;
  }
  switch (question.answerType) {
    case 'PLAYER':
      return 'GENERIC_PLAYER';
    case 'MATCH_RESULT':
      return 'GENERIC_MATCH_RESULT';
    case 'INTEGER':
      return 'GENERIC_INTEGER';
    case 'CHOICE':
      return 'GENERIC_CHOICE';
  }
}
