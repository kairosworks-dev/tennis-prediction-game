import { describe, expect, it } from 'vitest';
import { createDatabase, CURRENT_USER_ID } from './index';
import { snapshotKeys } from './scoreEntries';
import type { GameListState } from '../../types';

/**
 * Structural properties of the fixture set, not its contents.
 *
 * Nothing here asserts a name, a score or a count that an author might
 * reasonably want to change (AGENTS.md testing expectations). It asserts the
 * things the app depends on: that the three game states exist, that a draw is
 * internally coherent, and that two builds are identical.
 */
describe('fixture database', () => {
  it('covers the three game states step 1 requires', () => {
    const db = createDatabase();
    const now = Date.now();

    const states = new Set<GameListState>(
      db.tournaments.map((t) => {
        if (t.status === 'FINISHED') return 'FINISHED';
        if (t.status === 'RUNNING') return 'RUNNING';
        return Date.parse(t.signupDeadline) > now ? 'OPEN_FOR_SIGNUP' : 'RUNNING';
      }),
    );

    expect(states).toContain('OPEN_FOR_SIGNUP');
    expect(states).toContain('RUNNING');
    expect(states).toContain('FINISHED');
  });

  it('includes a two-draw Grand Slam that is mid-tournament', () => {
    const db = createDatabase();
    const running = db.tournaments.filter((t) => t.status === 'RUNNING');
    expect(running.length).toBeGreaterThan(0);

    const twoDraw = running.find((t) => db.draws.filter((d) => d.tournamentId === t.id).length === 2);
    expect(twoDraw).toBeDefined();
    expect(twoDraw?.category).toBe('GRAND_SLAM');

    const draws = db.draws.filter((d) => d.tournamentId === twoDraw?.id);
    expect(new Set(draws.map((d) => d.tour))).toEqual(new Set(['ATP', 'WTA']));

    // Mid-tournament means one group open and at least one already settled.
    const groups = db.betGroups.filter((g) => g.tournamentId === twoDraw?.id);
    expect(groups.filter((g) => g.status === 'OPEN')).toHaveLength(1);
    expect(groups.filter((g) => g.status === 'SETTLED').length).toBeGreaterThan(0);
  });

  it('gives the signed-in user a game to join and a game to play', () => {
    const db = createDatabase();
    const joined = new Set(
      db.participations.filter((p) => p.userId === CURRENT_USER_ID).map((p) => p.tournamentId),
    );
    const joinable = db.tournaments.filter(
      (t) => t.status === 'PUBLISHED' && !joined.has(t.id) && Date.parse(t.signupDeadline) > Date.now(),
    );
    expect(joined.size).toBeGreaterThan(0);
    expect(joinable.length).toBeGreaterThan(0);
  });

  it('builds every draw as eight equal sections that partition the field', () => {
    const db = createDatabase();
    for (const draw of db.draws) {
      const sections = db.sections.filter((s) => s.drawId === draw.id);
      expect(sections.map((s) => s.index).sort((a, b) => a - b)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);

      const entries = db.entries.filter((e) => e.drawId === draw.id);
      expect(entries).toHaveLength(draw.drawSize);
      expect(new Set(entries.map((e) => e.playerId)).size).toBe(entries.length);

      for (const section of sections) {
        expect(entries.filter((e) => e.sectionId === section.id)).toHaveLength(draw.drawSize / 8);
      }
    }
  });

  it('seeds each draw once per seed number, one top seed per section', () => {
    const db = createDatabase();
    for (const draw of db.draws) {
      const entries = db.entries.filter((e) => e.drawId === draw.id);
      const seeds = entries.map((e) => e.seed).filter((s): s is number => s !== null);
      expect(new Set(seeds).size).toBe(seeds.length);

      const topEight = entries.filter((e) => e.seed !== null && e.seed <= 8);
      expect(new Set(topEight.map((e) => e.sectionId)).size).toBe(topEight.length);
    }
  });

  it('records an outcome only for players who are actually in that draw', () => {
    const db = createDatabase();
    for (const outcome of db.outcomes) {
      const inDraw = db.entries.some(
        (e) => e.drawId === outcome.drawId && e.playerId === outcome.playerId,
      );
      expect(inDraw).toBe(true);
    }
  });

  it('writes a score entry only against a question the participant answered', () => {
    const db = createDatabase();
    const answered = new Set(db.predictions.map((p) => `${p.participationId}:${p.questionId}`));
    for (const score of db.scores) {
      expect(answered.has(`${score.participationId}:${score.questionId}`)).toBe(true);
    }
  });

  it('is deterministic — two builds produce identical data', () => {
    const a = createDatabase();
    const b = createDatabase();
    expect(b.entries).toEqual(a.entries);
    expect(b.outcomes).toEqual(a.outcomes);
    expect(b.predictions).toEqual(a.predictions);
    expect(b.scores).toEqual(a.scores);
  });

  it('hands each caller its own copy, so mutation cannot leak between tests', () => {
    const a = createDatabase();
    const before = a.tournaments.length;
    a.tournaments.pop();
    expect(createDatabase().tournaments).toHaveLength(before);
  });

  it('can start signed out', () => {
    expect(createDatabase({ signedIn: false }).sessionUserId).toBeNull();
  });
});

/**
 * The mock serves pre-computed score entries rather than computing them —
 * scoring is the backend's job. These guard the seam between the snapshot and
 * the generator that produced its inputs: if the fixtures change and nobody
 * regenerates, the snapshot goes stale, and a stale snapshot is worse than no
 * snapshot because it looks right.
 *
 * Regeneration is two commands, documented in scoreEntries.ts.
 */
describe('the score snapshot', () => {
  it('has no orphans — every entry names a prediction that exists', () => {
    const db = createDatabase();
    const answered = new Set(
      db.predictions.map((p) => `${p.participationId}:${p.questionId}`),
    );
    const orphans = [...snapshotKeys()].filter((key) => !answered.has(key));
    expect(orphans, 'snapshot is stale — regenerate it, see scoreEntries.ts').toEqual([]);
  });

  it('scores only questions in a settled group', () => {
    const db = createDatabase();
    const settled = new Set(
      db.betGroups.filter((g) => g.status === 'SETTLED').map((g) => g.id),
    );
    const groupOf = new Map(db.questions.map((q) => [q.id, q.betGroupId]));
    const wrongGroup = [...snapshotKeys()].filter((key) => {
      const questionId = key.slice(key.indexOf(':') + 1);
      const groupId = groupOf.get(questionId);
      return groupId === undefined || !settled.has(groupId);
    });
    expect(wrongGroup).toEqual([]);
  });

  it('covers the question kinds that have settled at the fixtures\u2019 stage', () => {
    const db = createDatabase();
    const kindOf = new Map(db.questions.map((q) => [q.id, q.kind]));
    const scoredKinds = new Set(
      [...snapshotKeys()].map((key) => kindOf.get(key.slice(key.indexOf(':') + 1))),
    );
    // A tournament at the quarter-finals has settled these three and not the
    // later ones; a snapshot missing them means it was regenerated wrongly.
    expect(scoredKinds).toContain('QF_PICKS');
    expect(scoredKinds).toContain('UNDERPERFORMER');
    expect(scoredKinds).toContain('BREAKOUT');
  });

  it('gives every awarded point a reason', () => {
    const db = createDatabase();
    expect(db.scores.length).toBeGreaterThan(0);
    expect(db.scores.every((s) => s.reason.trim().length > 0)).toBe(true);
  });

  it('leaves an unsettled question without an entry rather than a zero', () => {
    const db = createDatabase();
    const open = db.betGroups.filter((g) => g.status === 'OPEN').map((g) => g.id);
    const openQuestionIds = new Set(
      db.questions.filter((q) => open.includes(q.betGroupId)).map((q) => q.id),
    );
    expect(db.scores.filter((s) => openQuestionIds.has(s.questionId))).toEqual([]);
  });
});
