import type { ParticipationId, QuestionId } from '../../types';
import entries from './scoreEntries.json';

/**
 * Pre-computed score entries for the fixtures.
 *
 * Scoring is the backend's job (AGENTS.md rule 2) and the engine is a pure
 * function there (rule 5), so the mock does not compute points — it serves
 * them. This file is a snapshot produced by that engine over this fixture
 * data, and the mock hands it out the way a real API would hand out rows it
 * had written earlier.
 *
 * Regenerating it, after any change to the fixture generator:
 *
 *   cd frontend && npx vite-node scripts/exportScoringInputs.ts /tmp/inputs.json
 *   cd ../backend && uv run python scripts/score_fixture_inputs.py \\
 *       /tmp/inputs.json ../frontend/src/services/mock/fixtures/scoreEntries.json
 *
 * `fixtures.test.ts` fails if the snapshot and the generator disagree about
 * which questions are answered and settled, so drift is caught rather than
 * served.
 */
export interface FixtureScore {
  readonly points: number;
  readonly reason: string;
}

const byKey = new Map<string, FixtureScore>(
  entries.map((entry) => [
    `${entry.participationId}:${entry.questionId}`,
    { points: entry.points, reason: entry.reason },
  ]),
);

/** Null where the question has not settled — which is not the same as zero. */
export function fixtureScoreFor(
  participationId: ParticipationId,
  questionId: QuestionId,
): FixtureScore | null {
  return byKey.get(`${participationId}:${questionId}`) ?? null;
}

/** Every key in the snapshot, for the drift check. */
export function snapshotKeys(): ReadonlySet<string> {
  return new Set(byKey.keys());
}
