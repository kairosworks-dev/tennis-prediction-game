/**
 * Dumps the fixture scoring inputs so the backend's engine can produce the
 * score entries the mock serves.
 *
 *   npx vite-node scripts/exportScoringInputs.ts
 *
 * Tooling, not application code: it is outside `src/`, never bundled, and
 * nothing in the app imports it. It exists so that regenerating the committed
 * score snapshot is a documented two-command operation rather than folklore.
 */

import { writeFileSync } from 'node:fs';
import { createDatabase } from '../src/services/mock/fixtures/index';

const db = createDatabase();

const drawsByTournament = new Map<string, string[]>();
for (const draw of db.draws) {
  drawsByTournament.set(draw.tournamentId, [
    ...(drawsByTournament.get(draw.tournamentId) ?? []),
    draw.id,
  ]);
}

const correctByQuestion = new Map(db.questionOutcomes.map((o) => [o.questionId, o.correctAnswer]));
const settledGroupIds = new Set(db.betGroups.filter((g) => g.status === 'SETTLED').map((g) => g.id));
const questionById = new Map(db.questions.map((q) => [q.id, q]));
const participationById = new Map(db.participations.map((p) => [p.id, p]));

const games = db.tournaments.map((tournament) => {
  const drawIds = new Set(drawsByTournament.get(tournament.id) ?? []);
  const outcomes: Record<string, string> = {};
  for (const outcome of db.outcomes) {
    if (drawIds.has(outcome.drawId)) {
      outcomes[outcome.playerId] = outcome.roundReached;
    }
  }

  const answers = db.predictions
    .filter((prediction) => {
      const question = questionById.get(prediction.questionId);
      const participation = participationById.get(prediction.participationId);
      return (
        question !== undefined &&
        participation?.tournamentId === tournament.id &&
        settledGroupIds.has(question.betGroupId)
      );
    })
    .map((prediction) => ({
      participationId: prediction.participationId,
      questionId: prediction.questionId,
      payload: prediction.payload,
      correctAnswer: correctByQuestion.get(prediction.questionId) ?? null,
    }));

  return {
    tournamentId: tournament.id,
    scoringProfile: tournament.scoringProfile,
    outcomes,
    answers,
  };
});

const output = {
  playerNames: Object.fromEntries(db.players.map((p) => [p.id, p.fullName])),
  games,
  // What the TypeScript scorer currently produces, so the backend's output can
  // be diffed against it before that scorer is deleted.
  currentScores: db.scores.map((s) => ({
    participationId: s.participationId,
    questionId: s.questionId,
    points: s.points,
    reason: s.reason,
  })),
};

const target = process.argv[2] ?? 'scoring-inputs.json';
writeFileSync(target, `${JSON.stringify(output, null, 2)}\n`);
console.log(
  `wrote ${target}: ${games.length} games, ` +
    `${games.reduce((n, g) => n + g.answers.length, 0)} answers, ` +
    `${output.currentScores.length} current score entries`,
);
