import { describe, expect, it } from 'vitest';
import { samePayload } from './payloadEquality';
import type { PredictionPayload } from '../../services';

describe('samePayload', () => {
  it('treats two empty answers as the same and one empty as different', () => {
    expect(samePayload(null, null)).toBe(true);
    expect(samePayload(null, { kind: 'GENERIC_INTEGER', value: 0 })).toBe(false);
    expect(samePayload({ kind: 'GENERIC_INTEGER', value: 0 }, null)).toBe(false);
  });

  it('compares integers and player answers by value', () => {
    expect(samePayload({ kind: 'GENERIC_INTEGER', value: 2 }, { kind: 'GENERIC_INTEGER', value: 2 })).toBe(true);
    expect(samePayload({ kind: 'GENERIC_INTEGER', value: 2 }, { kind: 'GENERIC_INTEGER', value: 3 })).toBe(false);
    expect(samePayload({ kind: 'CHAMPION', playerId: 'a' }, { kind: 'CHAMPION', playerId: 'b' })).toBe(false);
  });

  it('does not tell kinds apart by shape alone', () => {
    expect(samePayload({ kind: 'CHAMPION', playerId: 'a' }, { kind: 'BREAKOUT', playerId: 'a' })).toBe(false);
  });

  it('does not depend on object key order', () => {
    const a = { kind: 'GENERIC_MATCH_RESULT', winnerId: 'w', setScore: '2-1' } as PredictionPayload;
    const b = { setScore: '2-1', winnerId: 'w', kind: 'GENERIC_MATCH_RESULT' } as PredictionPayload;
    expect(samePayload(a, b)).toBe(true);
    expect(samePayload(a, { ...b, setScore: '2-0' } as PredictionPayload)).toBe(false);
  });

  it('treats the same players in another order as the same answer', () => {
    expect(
      samePayload(
        { kind: 'SF_PICKS', playerIds: ['a', 'b', 'c', 'd'] },
        { kind: 'SF_PICKS', playerIds: ['d', 'c', 'b', 'a'] },
      ),
    ).toBe(true);
    expect(
      samePayload(
        { kind: 'FINALIST_PICKS', playerIds: ['a', 'b'] },
        { kind: 'FINALIST_PICKS', playerIds: ['a', 'c'] },
      ),
    ).toBe(false);
    expect(
      samePayload(
        { kind: 'QF_PICKS', picks: [{ sectionIndex: 2, playerId: 'b' }, { sectionIndex: 1, playerId: 'a' }] },
        { kind: 'QF_PICKS', picks: [{ playerId: 'a', sectionIndex: 1 }, { playerId: 'b', sectionIndex: 2 }] },
      ),
    ).toBe(true);
  });

  it('notices a pick moved to another section', () => {
    expect(
      samePayload(
        { kind: 'QF_PICKS', picks: [{ sectionIndex: 1, playerId: 'a' }] },
        { kind: 'QF_PICKS', picks: [{ sectionIndex: 2, playerId: 'a' }] },
      ),
    ).toBe(false);
  });
});
