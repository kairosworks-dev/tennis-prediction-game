import { describe, expect, it } from 'vitest';
import { validatePrediction, expectedPayloadKind, type ValidationContext } from './validation';
import { isApiError } from '../errors';
import type {
  Draw, DrawEntry, PlayerId, PredictionPayload, Question, TypedQuestionKind,
} from '../types';

/**
 * Spec 5.3, one rule at a time.
 *
 * These build their own minimal draw rather than reading the fixtures, so that
 * changing a fixture never rewrites a rule test.
 */

const DRAW: Draw = {
  id: 'draw-1', tournamentId: 't-1', tour: 'ATP', drawSize: 128, bestOf: 5,
  officialDrawUrl: null,
};

/** Eight sections, four entrants each: seeds 1-8, seeds 9-16, and two unseeded. */
function buildEntries(): DrawEntry[] {
  const entries: DrawEntry[] = [];
  for (let section = 1; section <= 8; section += 1) {
    const sectionId = `s-${String(section)}`;
    entries.push(
      { id: `e-a${String(section)}`, drawId: DRAW.id, sectionId, playerId: `seedA-${String(section)}`, seed: section },
      { id: `e-b${String(section)}`, drawId: DRAW.id, sectionId, playerId: `seedB-${String(section)}`, seed: section + 8 },
      { id: `e-c${String(section)}`, drawId: DRAW.id, sectionId, playerId: `free-${String(section)}`, seed: null },
      { id: `e-d${String(section)}`, drawId: DRAW.id, sectionId, playerId: `free2-${String(section)}`, seed: null },
    );
  }
  return entries;
}

const ENTRIES = buildEntries();

function question(kind: TypedQuestionKind | null, overrides: Partial<Question> = {}): Question {
  return {
    id: 'q-1', betGroupId: 'bg-1', drawId: DRAW.id,
    family: kind === null ? 'GENERIC' : 'TYPED', kind,
    prompt: 'test', answerType: 'PLAYER', options: null, matchup: null,
    pointsHint: '', deadlineOverride: null, position: 0,
    ...overrides,
  };
}

function context(q: Question, siblings: Partial<Record<TypedQuestionKind, PredictionPayload>> = {}): ValidationContext {
  return {
    question: q,
    draw: DRAW,
    entries: ENTRIES,
    siblingPayloads: new Map(Object.entries(siblings) as [TypedQuestionKind, PredictionPayload][]),
    questionsInGroup: [q],
    questionIdByKind: new Map(),
  };
}

function rejection(payload: PredictionPayload, ctx: ValidationContext): string {
  try {
    validatePrediction(payload, ctx);
  } catch (error) {
    if (isApiError(error)) {
      return error.problem.detail;
    }
    throw error;
  }
  throw new Error('expected the prediction to be rejected, but it was accepted');
}

const eightPicks = (playerIds: readonly PlayerId[]): PredictionPayload => ({
  kind: 'QF_PICKS',
  picks: playerIds.map((playerId, index) => ({ sectionIndex: index + 1, playerId })),
});

const ALL_SECTIONS = Array.from({ length: 8 }, (_, i) => `seedA-${String(i + 1)}`);

describe('quarter-final picks', () => {
  const q = question('QF_PICKS');

  it('accepts exactly one player per section, eight in total', () => {
    expect(() => { validatePrediction(eightPicks(ALL_SECTIONS), context(q)); }).not.toThrow();
  });

  it('rejects fewer than eight', () => {
    expect(rejection(eightPicks(ALL_SECTIONS.slice(0, 7)), context(q))).toMatch(/one player from each/i);
  });

  it('rejects two picks for the same section', () => {
    const payload: PredictionPayload = {
      kind: 'QF_PICKS',
      picks: [
        ...ALL_SECTIONS.slice(0, 7).map((playerId, index) => ({ sectionIndex: index + 1, playerId })),
        { sectionIndex: 1, playerId: 'seedB-1' },
      ],
    };
    expect(rejection(payload, context(q))).toMatch(/two picks/i);
  });

  it('rejects a player who is not in the draw', () => {
    expect(rejection(eightPicks(['ghost', ...ALL_SECTIONS.slice(1)]), context(q))).toMatch(/not in this draw/i);
  });

  it('rejects a player picked for a section they are not in', () => {
    const payload: PredictionPayload = {
      kind: 'QF_PICKS',
      picks: ALL_SECTIONS.map((playerId, index) => ({
        // Section 3's pick is attributed to section 4.
        sectionIndex: index === 2 ? 4 : index + 1,
        playerId,
      })),
    };
    expect(rejection(payload, context(q))).toMatch(/two picks|not in the section/i);
  });
});

describe('semi-final picks', () => {
  const q = question('SF_PICKS');
  const qfPicks = eightPicks(ALL_SECTIONS);

  it('accepts four drawn from the quarter-final picks', () => {
    const payload: PredictionPayload = { kind: 'SF_PICKS', playerIds: ALL_SECTIONS.slice(0, 4) };
    expect(() => { validatePrediction(payload, context(q, { QF_PICKS: qfPicks })); }).not.toThrow();
  });

  it('rejects a size other than four', () => {
    const payload: PredictionPayload = { kind: 'SF_PICKS', playerIds: ALL_SECTIONS.slice(0, 3) };
    expect(rejection(payload, context(q, { QF_PICKS: qfPicks }))).toMatch(/exactly 4/i);
  });

  it('rejects a player who is not among the quarter-final picks', () => {
    const payload: PredictionPayload = {
      kind: 'SF_PICKS',
      playerIds: [...ALL_SECTIONS.slice(0, 3), 'seedB-5'],
    };
    expect(rejection(payload, context(q, { QF_PICKS: qfPicks }))).toMatch(/must come from your quarter-finalists/i);
  });

  it('asks for the quarter-finals first when they are unanswered', () => {
    const payload: PredictionPayload = { kind: 'SF_PICKS', playerIds: ALL_SECTIONS.slice(0, 4) };
    expect(rejection(payload, context(q))).toMatch(/quarter-finalists question first/i);
  });
});

describe('finalist picks and champion', () => {
  const qfPicks = eightPicks(ALL_SECTIONS);
  const sfPicks: PredictionPayload = { kind: 'SF_PICKS', playerIds: ALL_SECTIONS.slice(0, 4) };
  const finalists: PredictionPayload = { kind: 'FINALIST_PICKS', playerIds: ALL_SECTIONS.slice(0, 2) };

  it('accepts two finalists drawn from the semi-finalists', () => {
    const ctx = context(question('FINALIST_PICKS'), { QF_PICKS: qfPicks, SF_PICKS: sfPicks });
    expect(() => { validatePrediction(finalists, ctx); }).not.toThrow();
  });

  it('rejects a finalist who is not a semi-finalist', () => {
    const ctx = context(question('FINALIST_PICKS'), { QF_PICKS: qfPicks, SF_PICKS: sfPicks });
    const payload: PredictionPayload = { kind: 'FINALIST_PICKS', playerIds: [ALL_SECTIONS[0] ?? '', 'seedA-8'] };
    expect(rejection(payload, ctx)).toMatch(/must come from your semi-finalists/i);
  });

  it('accepts a champion who is one of the two finalists', () => {
    const ctx = context(question('CHAMPION'), { FINALIST_PICKS: finalists });
    const payload: PredictionPayload = { kind: 'CHAMPION', playerId: ALL_SECTIONS[1] ?? '' };
    expect(() => { validatePrediction(payload, ctx); }).not.toThrow();
  });

  it('rejects a champion who is not a finalist', () => {
    const ctx = context(question('CHAMPION'), { FINALIST_PICKS: finalists });
    const payload: PredictionPayload = { kind: 'CHAMPION', playerId: 'seedA-7' };
    expect(rejection(payload, ctx)).toMatch(/must come from your finalists/i);
  });
});

describe('underperformer', () => {
  const q = question('UNDERPERFORMER');

  it('accepts a seed of ten or better', () => {
    const payload: PredictionPayload = { kind: 'UNDERPERFORMER', playerId: 'seedB-2' }; // seed 10
    expect(() => { validatePrediction(payload, context(q)); }).not.toThrow();
  });

  it('rejects a seed worse than ten', () => {
    const payload: PredictionPayload = { kind: 'UNDERPERFORMER', playerId: 'seedB-3' }; // seed 11
    expect(rejection(payload, context(q))).toMatch(/seeded 10 or better/i);
  });

  it('rejects an unseeded entrant', () => {
    const payload: PredictionPayload = { kind: 'UNDERPERFORMER', playerId: 'free-1' };
    expect(rejection(payload, context(q))).toMatch(/seeded 10 or better/i);
  });
});

describe('breakout', () => {
  const q = question('BREAKOUT');

  it('accepts an unseeded entrant', () => {
    const payload: PredictionPayload = { kind: 'BREAKOUT', playerId: 'free-4' };
    expect(() => { validatePrediction(payload, context(q)); }).not.toThrow();
  });

  it('rejects a seeded entrant', () => {
    const payload: PredictionPayload = { kind: 'BREAKOUT', playerId: 'seedA-1' };
    expect(rejection(payload, context(q))).toMatch(/must be an unseeded entrant/i);
  });
});

describe('set scores', () => {
  const matchQuestion = question(null, {
    answerType: 'MATCH_RESULT',
    matchup: ['seedA-1', 'seedA-2'],
  });

  it.each(['3-0', '3-1', '3-2'] as const)('accepts %s in a best-of-five draw', (setScore) => {
    const payload: PredictionPayload = { kind: 'GENERIC_MATCH_RESULT', winnerId: 'seedA-1', setScore };
    expect(() => { validatePrediction(payload, context(matchQuestion)); }).not.toThrow();
  });

  it.each(['2-0', '2-1'] as const)('rejects %s in a best-of-five draw', (setScore) => {
    const payload: PredictionPayload = { kind: 'GENERIC_MATCH_RESULT', winnerId: 'seedA-1', setScore };
    expect(rejection(payload, context(matchQuestion))).toMatch(/not a legal result/i);
  });

  it.each(['2-0', '2-1'] as const)('accepts %s in a best-of-three draw', (setScore) => {
    const ctx: ValidationContext = { ...context(matchQuestion), draw: { ...DRAW, bestOf: 3 } };
    const payload: PredictionPayload = { kind: 'GENERIC_MATCH_RESULT', winnerId: 'seedA-1', setScore };
    expect(() => { validatePrediction(payload, ctx); }).not.toThrow();
  });

  it.each(['3-0', '3-1', '3-2'] as const)('rejects %s in a best-of-three draw', (setScore) => {
    const ctx: ValidationContext = { ...context(matchQuestion), draw: { ...DRAW, bestOf: 3 } };
    const payload: PredictionPayload = { kind: 'GENERIC_MATCH_RESULT', winnerId: 'seedA-1', setScore };
    expect(rejection(payload, ctx)).toMatch(/not a legal result/i);
  });

  it('rejects a winner who is not in the tie', () => {
    const payload: PredictionPayload = { kind: 'GENERIC_MATCH_RESULT', winnerId: 'seedA-5', setScore: '3-0' };
    expect(rejection(payload, context(matchQuestion))).toMatch(/one of the two players/i);
  });
});

describe('expectedPayloadKind', () => {
  it('uses the typed kind for a typed question', () => {
    expect(expectedPayloadKind(question('BREAKOUT'))).toBe('BREAKOUT');
  });

  it.each([
    ['PLAYER', 'GENERIC_PLAYER'],
    ['MATCH_RESULT', 'GENERIC_MATCH_RESULT'],
    ['INTEGER', 'GENERIC_INTEGER'],
    ['CHOICE', 'GENERIC_CHOICE'],
  ] as const)('maps the %s answer type to %s', (answerType, expected) => {
    expect(expectedPayloadKind(question(null, { answerType }))).toBe(expected);
  });
});
