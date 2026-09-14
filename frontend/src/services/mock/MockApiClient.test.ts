import { beforeEach, describe, expect, it } from 'vitest';
import { MockApiClient } from './MockApiClient';
import { isApiError } from '../errors';
import type { ApiClient } from '../apiClient';
import type { PredictionPayload, TournamentId } from '../types';

/**
 * The service layer as the application sees it: through the `ApiClient`
 * interface, never the concrete class. Latency is off so tests stay fast.
 */
function client(options: { signedIn?: boolean; asAdmin?: boolean } = {}): MockApiClient {
  return new MockApiClient({ ...options, latencyMs: 0 });
}

/** The running two-draw game, found by shape rather than by name. */
async function runningGame(api: ApiClient): Promise<TournamentId> {
  const summaries = await api.listTournaments();
  const running = summaries.find((s) => s.state === 'RUNNING' && s.participationId !== null);
  if (running === undefined) {
    throw new Error('fixtures no longer contain a running game the user has joined');
  }
  return running.tournament.id;
}

async function expectRejection(promise: Promise<unknown>): Promise<{ status: number; detail: string }> {
  try {
    await promise;
  } catch (error) {
    if (isApiError(error)) {
      return { status: error.status, detail: error.problem.detail };
    }
    throw error;
  }
  throw new Error('expected the call to reject, but it resolved');
}

describe('the ApiClient contract', () => {
  it('is satisfied by MockApiClient', () => {
    const api: ApiClient = client();
    expect(typeof api.listTournaments).toBe('function');
  });
});

describe('authentication', () => {
  it('returns null rather than throwing for an anonymous visitor', async () => {
    await expect(client({ signedIn: false }).getCurrentUser()).resolves.toBeNull();
  });

  it('refuses a signed-out caller with 401', async () => {
    const { status } = await expectRejection(client({ signedIn: false }).listTournaments());
    expect(status).toBe(401);
  });

  it('registers an account that still needs email verification', async () => {
    const api = client({ signedIn: false });
    const result = await api.register({
      email: 'new@example.com', password: 'a-long-enough-password', displayName: 'Newcomer',
    });
    expect(result.requiresEmailVerification).toBe(true);
    expect(result.user.emailVerifiedAt).toBeNull();
  });

  it('rejects a duplicate email with 409', async () => {
    const api = client({ signedIn: false });
    const existing = api.database.users[0];
    const { status } = await expectRejection(
      api.register({ email: existing?.email ?? '', password: 'a-long-enough-password', displayName: 'Twin' }),
    );
    expect(status).toBe(409);
  });

  it('reports field-level problems for a short password', async () => {
    const api = client({ signedIn: false });
    try {
      await api.register({ email: 'x@example.com', password: 'short', displayName: 'X' });
      throw new Error('expected rejection');
    } catch (error) {
      expect(isApiError(error) && error.fieldErrors['password']).toBeDefined();
    }
  });

  it('does not reveal whether an address has an account on password reset', async () => {
    const api = client({ signedIn: false });
    await expect(api.requestPasswordReset({ email: 'nobody@example.com' })).resolves.toBeUndefined();
  });

  it('anonymises rather than deletes, so past leaderboards survive', async () => {
    const api = client();
    const before = api.database.users.length;
    const me = await api.getCurrentUser();
    await api.deleteCurrentUser();
    expect(api.database.users).toHaveLength(before);
    const after = api.database.users.find((u) => u.id === me?.id);
    expect(after?.displayName).not.toBe(me?.displayName);
    expect(after?.isActive).toBe(false);
  });
});

describe('the landing page teaser', () => {
  it('needs no session and points at a game still open for signup', async () => {
    const teaser = await client({ signedIn: false }).getNextGame();
    expect(teaser).not.toBeNull();
    expect(Date.parse(teaser?.signupDeadline ?? '')).toBeGreaterThan(Date.now());
  });
});

describe('joining a game', () => {
  it('rejects a join once the signup deadline has passed', async () => {
    const api = client();
    const closed = api.database.tournaments.find((t) => Date.parse(t.signupDeadline) < Date.now());
    const { status } = await expectRejection(
      api.joinTournament({ tournamentId: closed?.id ?? '' }),
    );
    expect(status).toBe(403);
  });

  it('rejects a private game without the right join code', async () => {
    const api = client();
    const priv = api.database.tournaments.find((t) => t.visibility === 'PRIVATE');
    const { status } = await expectRejection(
      api.joinTournament({ tournamentId: priv?.id ?? '', joinCode: 'WRONG' }),
    );
    expect(status).toBe(422);
  });

  it('accepts a private game with the right join code', async () => {
    const api = client();
    const priv = api.database.tournaments.find((t) => t.visibility === 'PRIVATE');
    const participation = await api.joinTournament({
      tournamentId: priv?.id ?? '', joinCode: priv?.joinCode ?? '',
    });
    expect(participation.tournamentId).toBe(priv?.id);
  });

  it('refuses to join twice', async () => {
    const api = client();
    const open = (await api.listTournaments()).find(
      (s) => s.state === 'OPEN_FOR_SIGNUP' && s.participationId === null
        && s.tournament.visibility === 'PUBLIC',
    );
    await api.joinTournament({ tournamentId: open?.tournament.id ?? '' });
    const { status } = await expectRejection(
      api.joinTournament({ tournamentId: open?.tournament.id ?? '' }),
    );
    expect(status).toBe(409);
  });

  it('hides a private game from someone who has not joined it', async () => {
    const api = client();
    const priv = api.database.tournaments.find((t) => t.visibility === 'PRIVATE');
    const listed = (await api.listTournaments()).some((s) => s.tournament.id === priv?.id);
    expect(listed).toBe(false);
  });

  it('never shows a join code to a participant', async () => {
    const api = client();
    const priv = api.database.tournaments.find((t) => t.visibility === 'PRIVATE');
    await api.joinTournament({ tournamentId: priv?.id ?? '', joinCode: priv?.joinCode ?? '' });
    const detail = await api.getTournament(priv?.id ?? '');
    expect(detail.tournament.joinCode).toBeNull();
  });
});

describe('predictions', () => {
  let api: MockApiClient;
  let tournamentId: TournamentId;

  beforeEach(async () => {
    api = client();
    tournamentId = await runningGame(api);
  });

  async function openGroupQuestion(answerType: 'MATCH_RESULT') {
    const groups = await api.listBetGroups(tournamentId);
    const open = groups.find((g) => g.status === 'OPEN');
    const questions = await api.listQuestions(tournamentId, open?.id ?? '');
    const question = questions.find((q) => q.answerType === answerType);
    if (question === undefined) {
      throw new Error('the open group no longer has a match-result question');
    }
    return question;
  }

  it('accepts an answer to a question in the open group', async () => {
    const question = await openGroupQuestion('MATCH_RESULT');
    const draw = api.database.draws.find((d) => d.id === question.drawId);
    const payload: PredictionPayload = {
      kind: 'GENERIC_MATCH_RESULT',
      winnerId: question.matchup?.[0] ?? '',
      setScore: draw?.bestOf === 5 ? '3-1' : '2-1',
    };
    const saved = await api.putPrediction({ tournamentId, questionId: question.id, payload, asDraft: false });
    expect(saved.payload).toEqual(payload);
    expect(saved.submittedAt).not.toBeNull();
  });

  it('marks a draft as unsubmitted', async () => {
    const question = await openGroupQuestion('MATCH_RESULT');
    const draw = api.database.draws.find((d) => d.id === question.drawId);
    const saved = await api.putPrediction({
      tournamentId,
      questionId: question.id,
      payload: {
        kind: 'GENERIC_MATCH_RESULT',
        winnerId: question.matchup?.[0] ?? '',
        setScore: draw?.bestOf === 5 ? '3-0' : '2-0',
      },
      asDraft: true,
    });
    expect(saved.submittedAt).toBeNull();
  });

  it('replaces rather than duplicates a repeated answer', async () => {
    const question = await openGroupQuestion('MATCH_RESULT');
    const draw = api.database.draws.find((d) => d.id === question.drawId);
    const base = { tournamentId, questionId: question.id, asDraft: false } as const;
    const first = await api.putPrediction({
      ...base,
      payload: { kind: 'GENERIC_MATCH_RESULT', winnerId: question.matchup?.[0] ?? '', setScore: draw?.bestOf === 5 ? '3-0' : '2-0' },
    });
    const second = await api.putPrediction({
      ...base,
      payload: { kind: 'GENERIC_MATCH_RESULT', winnerId: question.matchup?.[1] ?? '', setScore: draw?.bestOf === 5 ? '3-2' : '2-1' },
    });
    expect(second.id).toBe(first.id);
    const mine = await api.listOwnPredictions(tournamentId);
    expect(mine.filter((p) => p.questionId === question.id)).toHaveLength(1);
  });

  it('rejects an answer to a group that has already locked', async () => {
    // The tournament group is settled too but carries only typed questions, so
    // look for a settled group that actually has a match to call.
    const groups = await api.listBetGroups(tournamentId);
    let question: Awaited<ReturnType<ApiClient['listQuestions']>>[number] | undefined;
    for (const group of groups.filter((g) => g.status === 'SETTLED')) {
      const questions = await api.listQuestions(tournamentId, group.id);
      question = questions.find((q) => q.answerType === 'MATCH_RESULT');
      if (question !== undefined) {
        break;
      }
    }
    expect(question).toBeDefined();
    const { status, detail } = await expectRejection(
      api.putPrediction({
        tournamentId,
        questionId: question?.id ?? '',
        payload: { kind: 'GENERIC_MATCH_RESULT', winnerId: question?.matchup?.[0] ?? '', setScore: '3-0' },
        asDraft: false,
      }),
    );
    expect(status).toBe(403);
    expect(detail).toMatch(/closed/i);
  });

  it('rejects a payload whose shape does not match the question', async () => {
    const question = await openGroupQuestion('MATCH_RESULT');
    const { status } = await expectRejection(
      api.putPrediction({
        tournamentId,
        questionId: question.id,
        payload: { kind: 'GENERIC_INTEGER', value: 3 },
        asDraft: false,
      }),
    );
    expect(status).toBe(422);
  });
});

describe('prediction visibility', () => {
  it("hides everyone else's answers while the group is open", async () => {
    const api = client();
    const tournamentId = await runningGame(api);
    const groups = await api.listBetGroups(tournamentId);
    const open = groups.find((g) => g.status === 'OPEN');
    const questions = await api.listQuestions(tournamentId, open?.id ?? '');
    const { status } = await expectRejection(
      api.listQuestionPredictions(tournamentId, questions[0]?.id ?? ''),
    );
    expect(status).toBe(403);
  });

  it('opens them once the group has settled', async () => {
    const api = client();
    const tournamentId = await runningGame(api);
    const groups = await api.listBetGroups(tournamentId);
    const settled = groups.find((g) => g.status === 'SETTLED');
    const questions = await api.listQuestions(tournamentId, settled?.id ?? '');
    const rows = await api.listQuestionPredictions(tournamentId, questions[0]?.id ?? '');
    expect(rows.length).toBeGreaterThan(1);
    expect(rows.every((r) => typeof r.displayName === 'string')).toBe(true);
  });
});

describe('ranking', () => {
  it('orders by total points, descending', async () => {
    const api = client();
    const ranking = await api.getRanking(await runningGame(api));
    const totals = ranking.map((r) => r.totalPoints);
    expect([...totals].sort((a, b) => b - a)).toEqual(totals);
  });

  it('gives tied participants the same position and skips the next', async () => {
    const api = client();
    const ranking = await api.getRanking(await runningGame(api));

    for (const entry of ranking) {
      const sameScore = ranking.filter((r) => r.totalPoints === entry.totalPoints);
      // Everyone on a given score shares one position...
      expect(new Set(sameScore.map((r) => r.position)).size).toBe(1);
    }
    // ...and a position is always one more than the number of people above.
    for (const entry of ranking) {
      const above = ranking.filter((r) => r.totalPoints > entry.totalPoints).length;
      expect(entry.position).toBe(above + 1);
    }
  });

  it('marks exactly one row as the current user', async () => {
    const api = client();
    const ranking = await api.getRanking(await runningGame(api));
    expect(ranking.filter((r) => r.isCurrentUser)).toHaveLength(1);
  });

  it('agrees with the score breakdown on the total and the position', async () => {
    const api = client();
    const tournamentId = await runningGame(api);
    const [ranking, breakdown] = await Promise.all([
      api.getRanking(tournamentId),
      api.getScoreBreakdown(tournamentId),
    ]);
    const mine = ranking.find((r) => r.isCurrentUser);
    expect(breakdown.total).toBe(mine?.totalPoints);
    expect(breakdown.position).toBe(mine?.position);
  });

  it('adds the per-group points up to the total', async () => {
    const api = client();
    const ranking = await api.getRanking(await runningGame(api));
    for (const entry of ranking) {
      const summed = entry.perGroupPoints.reduce((total, g) => total + g.points, 0);
      expect(summed).toBe(entry.totalPoints);
    }
  });
});

describe('the score breakdown', () => {
  it('shows a reason beside every awarded point', async () => {
    const api = client();
    const breakdown = await api.getScoreBreakdown(await runningGame(api));
    const scored = breakdown.groups.flatMap((g) => g.rows).filter((r) => r.points !== null);
    expect(scored.length).toBeGreaterThan(0);
    expect(scored.every((r) => (r.reason ?? '').length > 0)).toBe(true);
  });

  it('leaves an unsettled question without points rather than showing a zero', async () => {
    const api = client();
    const breakdown = await api.getScoreBreakdown(await runningGame(api));
    const openBlock = breakdown.groups.find((g) => g.betGroup.status === 'OPEN');
    expect(openBlock?.rows.every((r) => r.points === null)).toBe(true);
    expect(openBlock?.comparisonAvailable).toBe(false);
  });

  it('adds each block up to its own subtotal', async () => {
    const api = client();
    const breakdown = await api.getScoreBreakdown(await runningGame(api));
    for (const block of breakdown.groups) {
      const summed = block.rows.reduce((total, row) => total + (row.points ?? 0), 0);
      expect(block.subtotal).toBe(summed);
    }
  });
});

describe('admin authorisation', () => {
  it('refuses an organiser action to a participant', async () => {
    const api = client();
    const { status } = await expectRejection(api.listUsers({}));
    expect(status).toBe(403);
  });

  it('allows it for an organiser', async () => {
    const api = client({ asAdmin: true });
    const page = await api.listUsers({ limit: 5 });
    expect(page.items.length).toBeGreaterThan(0);
    expect(page.total).toBeGreaterThanOrEqual(page.items.length);
  });

  it('stops an organiser removing their own rights', async () => {
    const api = client({ asAdmin: true });
    const me = await api.getCurrentUser();
    const { status } = await expectRejection(
      api.updateUser({ userId: me?.id ?? '', isAdmin: false }),
    );
    expect(status).toBe(409);
  });

  it('rebuilds the outcome grid in place rather than appending to it', async () => {
    const api = client({ asAdmin: true });
    const draw = api.database.draws[0];
    const entries = api.database.entries.filter((e) => e.drawId === draw?.id).slice(0, 3);
    const updated = await api.putDrawOutcomes({
      drawId: draw?.id ?? '',
      entries: entries.map((e) => ({ playerId: e.playerId, roundReached: 'R64' as const, note: null })),
    });
    expect(api.database.outcomes.filter((o) => o.drawId === draw?.id)).toHaveLength(3);
    expect(updated.length).toBe(8);
  });

  it('reports recalculation as idempotent bookkeeping', async () => {
    const api = client({ asAdmin: true });
    const tournamentId = api.database.tournaments[0]?.id ?? '';
    const first = await api.recalculateScores(tournamentId);
    const second = await api.recalculateScores(tournamentId);
    expect(second.scoreEntriesWritten).toBe(first.scoreEntriesWritten);
  });
});
