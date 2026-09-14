import type {
  BetGroup, Draw, DrawEntry, DrawSection, OutcomeEntry, Participation,
  PlayerId, Prediction, PredictionPayload, Question, QuestionOutcome,
  RoundReached, ScoreEntry, ScoringProfile, SetScore, Tour, Tournament,
  TournamentCategory, TournamentStatus, TournamentVisibility, Surface, User,
  MatchFormat,
} from '../../types';
import { createRandom, daysFromNow, dateOnly, hoursFromNow, id, shuffle } from './seed';
import { ALL_PLAYERS, playersForTour } from './players';
import { roundRank, scorePrediction } from './fixtureScoring';

const SECTIONS_PER_DRAW = 8;
const ENTRIES_PER_SECTION = 16;
const SEEDS_PER_DRAW = 32;

/** The default profile shipped with a new tournament (spec 5.1). */
export const DEFAULT_SCORING_PROFILE: ScoringProfile = {
  quarterFinalistPoints: 1,
  semiFinalistPoints: 2,
  finalistPoints: 3,
  championPoints: 5,
  underperformerPoints: [3, 2, 1],
  breakoutPoints: [2, 3, 4, 5, 7],
  featuredMatchWinnerPoints: 1,
  featuredMatchSetScorePoints: 1,
};

/** How far the tournament has got, which drives the outcome grid. */
export type GameStage = 'NOT_STARTED' | 'QUARTER_FINALS' | 'COMPLETE';

export interface DrawSpec {
  readonly tour: Tour;
  readonly bestOf: MatchFormat;
  readonly officialDrawUrl: string | null;
}

export interface GameSpec {
  readonly key: string;
  readonly name: string;
  readonly category: TournamentCategory;
  readonly surface: Surface;
  readonly location: string;
  readonly startInDays: number;
  readonly endInDays: number;
  readonly signupDeadlineInDays: number;
  readonly status: TournamentStatus;
  readonly visibility: TournamentVisibility;
  readonly joinCode: string | null;
  readonly rulesMarkdown: string;
  readonly draws: readonly DrawSpec[];
  readonly stage: GameStage;
  /** Users who have joined. The first is treated as the fixture's own player. */
  readonly participants: readonly User[];
  readonly randomSeed: number;
}

export interface BuiltGame {
  readonly tournament: Tournament;
  readonly draws: readonly Draw[];
  readonly sections: readonly DrawSection[];
  readonly entries: readonly DrawEntry[];
  readonly outcomes: readonly OutcomeEntry[];
  readonly participations: readonly Participation[];
  readonly betGroups: readonly BetGroup[];
  readonly questions: readonly Question[];
  readonly questionOutcomes: readonly QuestionOutcome[];
  readonly predictions: readonly Prediction[];
  readonly scores: readonly ScoreEntry[];
}

const TYPED_QUESTIONS = [
  { kind: 'QF_PICKS', prompt: 'Quarter-finalists — one player from each of the eight sections', answerType: 'PLAYER', pointsHint: '1 pt each' },
  { kind: 'SF_PICKS', prompt: 'Semi-finalists — four, from your quarter-finalists', answerType: 'PLAYER', pointsHint: '2 pts each' },
  { kind: 'FINALIST_PICKS', prompt: 'Finalists — two, from your semi-finalists', answerType: 'PLAYER', pointsHint: '3 pts each' },
  { kind: 'CHAMPION', prompt: 'Champion — one of your two finalists', answerType: 'PLAYER', pointsHint: '5 pts' },
  { kind: 'UNDERPERFORMER', prompt: 'Underperformer — a seed of ten or better who goes out early', answerType: 'PLAYER', pointsHint: '3 / 2 / 1' },
  { kind: 'BREAKOUT', prompt: 'Breakout — an unseeded entrant who runs', answerType: 'PLAYER', pointsHint: '2 / 3 / 4 / 5 / 7' },
] as const;

/** Round numbers a 128 draw actually plays, with the names people use. */
const ROUND_TITLES: readonly (readonly [number, string])[] = [
  [1, 'Round 1'], [2, 'Round 2'], [3, 'Round 3'], [4, 'Round 4'],
  [5, 'Quarter-finals'], [6, 'Semi-finals'], [7, 'Final'],
];

/** How far a player must have got to appear in round N's featured match. */
const MINIMUM_ROUND_BY_ROUND_NUMBER: Readonly<Record<number, RoundReached>> = {
  1: 'R128', 2: 'R64', 3: 'R32', 4: 'R16', 5: 'QF', 6: 'SF', 7: 'F',
};

/** Rounds already played when the game is at the given stage. */
function settledRounds(stage: GameStage): number {
  return stage === 'COMPLETE' ? 7 : stage === 'QUARTER_FINALS' ? 4 : 0;
}

interface DrawBuild {
  readonly draw: Draw;
  readonly sections: readonly DrawSection[];
  readonly entries: readonly DrawEntry[];
  /** Section index (1..8) to its entrants, seeded first. */
  readonly bySection: ReadonlyMap<number, readonly DrawEntry[]>;
  readonly outcomes: ReadonlyMap<PlayerId, RoundReached>;
}

function buildDraw(spec: GameSpec, drawSpec: DrawSpec, seedOffset: number): DrawBuild {
  const random = createRandom(spec.randomSeed + seedOffset);
  const drawId = id(spec.key, drawSpec.tour.toLowerCase());
  const pool = playersForTour(drawSpec.tour);

  const draw: Draw = {
    id: drawId,
    tournamentId: spec.key,
    tour: drawSpec.tour,
    drawSize: SECTIONS_PER_DRAW * ENTRIES_PER_SECTION,
    bestOf: drawSpec.bestOf,
    officialDrawUrl: drawSpec.officialDrawUrl,
  };

  const sections: DrawSection[] = [];
  const entries: DrawEntry[] = [];
  const bySection = new Map<number, DrawEntry[]>();

  // Seeds 1..32 are spread one per section per pass, the way a real draw places
  // them: seeds 1-8 head a section each, then 9-16, and so on.
  // The named players are the seeds, in ranking order — shuffling the whole
  // pool first would hand seed 1 to a random unknown, which is exactly what a
  // draw never does.
  const seeded = pool.slice(0, SEEDS_PER_DRAW);
  const unseeded = shuffle(random, pool.slice(SEEDS_PER_DRAW));
  let unseededCursor = 0;

  for (let sectionIndex = 1; sectionIndex <= SECTIONS_PER_DRAW; sectionIndex += 1) {
    const sectionId = id(drawId, 'section', sectionIndex);
    sections.push({ id: sectionId, drawId, index: sectionIndex });
    const sectionEntries: DrawEntry[] = [];

    for (let pass = 0; pass < SEEDS_PER_DRAW / SECTIONS_PER_DRAW; pass += 1) {
      const seedNumber = pass * SECTIONS_PER_DRAW + sectionIndex;
      const player = seeded[seedNumber - 1];
      if (player === undefined) {
        continue;
      }
      sectionEntries.push({
        id: id(drawId, 'e', player.id),
        drawId,
        sectionId,
        playerId: player.id,
        seed: seedNumber,
      });
    }

    while (sectionEntries.length < ENTRIES_PER_SECTION) {
      const player = unseeded[unseededCursor];
      unseededCursor += 1;
      if (player === undefined) {
        break;
      }
      sectionEntries.push({
        id: id(drawId, 'e', player.id),
        drawId,
        sectionId,
        playerId: player.id,
        seed: null,
      });
    }

    entries.push(...sectionEntries);
    bySection.set(sectionIndex, sectionEntries);
  }

  return { draw, sections, entries, bySection, outcomes: assignOutcomes(spec, bySection, random) };
}

/**
 * Who got how far. Within a 16-entrant section, one round eliminates half:
 * eight lose in R128, four in R64, two in R32, one in R16, and one comes out
 * as the section's quarter-finalist. Beyond the quarters the eight survivors
 * are narrowed the same way.
 */
function assignOutcomes(
  spec: GameSpec,
  bySection: ReadonlyMap<number, readonly DrawEntry[]>,
  random: () => number,
): ReadonlyMap<PlayerId, RoundReached> {
  const outcomes = new Map<PlayerId, RoundReached>();
  if (spec.stage === 'NOT_STARTED') {
    return outcomes;
  }

  const quarterFinalists: PlayerId[] = [];
  const losersByRound: readonly [RoundReached, number][] = [['R128', 8], ['R64', 4], ['R32', 2], ['R16', 1]];

  for (const [, sectionEntries] of [...bySection].sort((a, b) => a[0] - b[0])) {
    // The section is won by one of its top two seeds two times in three, which
    // keeps the fixture plausible without making every pick a formality.
    const ordered = shuffle(random, sectionEntries);
    const favourites = sectionEntries.filter((e) => e.seed !== null).slice(0, 2);
    const winner = random() < 0.66 && favourites.length > 0
      ? (favourites[Math.floor(random() * favourites.length)] ?? ordered[0])
      : ordered[0];
    if (winner === undefined) {
      continue;
    }
    quarterFinalists.push(winner.playerId);

    const rest = shuffle(random, sectionEntries.filter((e) => e.playerId !== winner.playerId));
    let cursor = 0;
    for (const [round, count] of losersByRound) {
      for (let i = 0; i < count; i += 1) {
        const entry = rest[cursor];
        cursor += 1;
        if (entry !== undefined) {
          outcomes.set(entry.playerId, round);
        }
      }
    }
    outcomes.set(winner.playerId, 'QF');
  }

  if (spec.stage === 'COMPLETE') {
    const order = shuffle(random, quarterFinalists);
    const survivors = order.slice(0, 4);
    survivors.forEach((pid) => outcomes.set(pid, 'SF'));
    const finalists = survivors.slice(0, 2);
    finalists.forEach((pid) => outcomes.set(pid, 'F'));
    const champion = finalists[0];
    if (champion !== undefined) {
      outcomes.set(champion, 'CHAMPION');
    }
  }

  return outcomes;
}


/* -------------------------------------------------------------------------
 * Bet groups, questions, predictions and the score entries that follow
 * ---------------------------------------------------------------------- */

interface GroupPlan {
  readonly group: BetGroup;
  readonly settled: boolean;
  readonly open: boolean;
}

function planGroups(spec: GameSpec): readonly GroupPlan[] {
  const played = settledRounds(spec.stage);
  const plans: GroupPlan[] = [];

  const tournamentSettled = spec.stage !== 'NOT_STARTED';
  plans.push({
    group: {
      id: id(spec.key, 'bg', 'tournament'),
      tournamentId: spec.key,
      kind: 'TOURNAMENT',
      round: null,
      title: 'Tournament bets',
      introMarkdown:
        'Submitted once per draw, before a ball is struck. Sections first, then narrow it down.',
      deadline: daysFromNow(spec.startInDays),
      status: tournamentSettled ? 'SETTLED' : 'OPEN',
    },
    settled: tournamentSettled,
    open: !tournamentSettled,
  });

  for (const [round, title] of ROUND_TITLES) {
    if (round > played + 1) {
      break;
    }
    const isSettled = round <= played;
    const isOpen = round === played + 1 && spec.stage !== 'NOT_STARTED' && spec.stage !== 'COMPLETE';
    if (!isSettled && !isOpen) {
      continue;
    }
    plans.push({
      group: {
        id: id(spec.key, 'bg', 'r', round),
        tournamentId: spec.key,
        kind: 'ROUND',
        round,
        title,
        introMarkdown: isOpen
          ? 'Quarters on both sides this week. Call the featured ties and the extra question.'
          : `Bets for ${title.toLowerCase()}.`,
        // A settled round closed in the past; the open one closes in five hours.
        deadline: isOpen ? hoursFromNow(5.2) : daysFromNow(spec.startInDays + round),
        status: isSettled ? 'SETTLED' : 'OPEN',
      },
      settled: isSettled,
      open: isOpen,
    });
  }

  // One group the participant can see coming but not yet answer.
  const next = ROUND_TITLES.find(([round]) => round === played + 2);
  if (next !== undefined && spec.stage === 'QUARTER_FINALS') {
    plans.push({
      group: {
        id: id(spec.key, 'bg', 'r', next[0]),
        tournamentId: spec.key,
        kind: 'ROUND',
        round: next[0],
        title: next[1],
        introMarkdown: '',
        deadline: daysFromNow(spec.startInDays + next[0]),
        status: 'DRAFT',
      },
      settled: false,
      open: false,
    });
  }

  return plans;
}

function buildQuestions(
  spec: GameSpec,
  plans: readonly GroupPlan[],
  builds: readonly DrawBuild[],
): readonly Question[] {
  const questions: Question[] = [];

  for (const plan of plans) {
    if (plan.group.kind === 'TOURNAMENT') {
      builds.forEach((build, drawIndex) => {
        TYPED_QUESTIONS.forEach((template, questionIndex) => {
          questions.push({
            id: id(plan.group.id, build.draw.tour.toLowerCase(), template.kind.toLowerCase()),
            betGroupId: plan.group.id,
            drawId: build.draw.id,
            family: 'TYPED',
            kind: template.kind,
            prompt: template.prompt,
            answerType: template.answerType,
            options: null,
            matchup: null,
            pointsHint: template.pointsHint,
            deadlineOverride: null,
            position: drawIndex * TYPED_QUESTIONS.length + questionIndex,
          });
        });
      });
      continue;
    }

    const random = createRandom(spec.randomSeed + (plan.group.round ?? 0) * 977);
    builds.forEach((build, drawIndex) => {
      // The featured tie is between two players who actually reached this round.
      // Picking from everyone who played produces a quarter-final between two
      // first-round losers, which is the kind of detail that makes a mock
      // useless for judging the screen.
      const floor = MINIMUM_ROUND_BY_ROUND_NUMBER[plan.group.round ?? 1] ?? 'R128';
      const alive = build.entries.filter(
        (e) => roundRank(build.outcomes.get(e.playerId) ?? null) >= roundRank(floor),
      );
      const candidates = shuffle(random, alive.length >= 2 ? alive : build.entries);
      const [a, b] = candidates;
      if (a === undefined || b === undefined) {
        return;
      }
      questions.push({
        id: id(plan.group.id, build.draw.tour.toLowerCase(), 'featured'),
        betGroupId: plan.group.id,
        drawId: build.draw.id,
        family: 'GENERIC',
        kind: null,
        prompt: `Featured match — ${build.draw.tour}`,
        answerType: 'MATCH_RESULT',
        options: null,
        matchup: [a.playerId, b.playerId],
        pointsHint: '1 + 1 pt',
        deadlineOverride: null,
        position: drawIndex,
      });
    });

    // Every other round carries an admin-composed extra question.
    if ((plan.group.round ?? 0) % 2 === 1) {
      questions.push({
        id: id(plan.group.id, 'extra'),
        betGroupId: plan.group.id,
        drawId: null,
        family: 'GENERIC',
        kind: null,
        prompt: 'How many of the four men\u2019s ties go to a deciding set?',
        answerType: 'INTEGER',
        options: null,
        matchup: null,
        pointsHint: '2 pts',
        deadlineOverride: null,
        position: builds.length,
      });
    }
  }

  return questions;
}

function buildQuestionOutcomes(
  spec: GameSpec,
  plans: readonly GroupPlan[],
  questions: readonly Question[],
  builds: readonly DrawBuild[],
): readonly QuestionOutcome[] {
  const settledGroupIds = new Set(plans.filter((p) => p.settled).map((p) => p.group.id));
  const buildByDraw = new Map(builds.map((b) => [b.draw.id, b]));
  const outcomes: QuestionOutcome[] = [];

  for (const question of questions) {
    if (!settledGroupIds.has(question.betGroupId) || question.family !== 'GENERIC') {
      continue;
    }
    const random = createRandom(spec.randomSeed + question.id.length * 31 + question.position);

    if (question.answerType === 'MATCH_RESULT' && question.matchup !== null) {
      const build = question.drawId === null ? undefined : buildByDraw.get(question.drawId);
      const format = build?.draw.bestOf ?? 3;
      const legal: readonly SetScore[] = format === 5 ? ['3-0', '3-1', '3-2'] : ['2-0', '2-1'];
      const winner = question.matchup[random() < 0.5 ? 0 : 1];
      const setScore = legal[Math.floor(random() * legal.length)] ?? legal[0];
      if (setScore === undefined) {
        continue;
      }
      outcomes.push({
        questionId: question.id,
        correctAnswer: { kind: 'GENERIC_MATCH_RESULT', winnerId: winner, setScore },
        settledAt: daysFromNow(spec.startInDays + 1),
        note: null,
      });
      continue;
    }

    if (question.answerType === 'INTEGER') {
      outcomes.push({
        questionId: question.id,
        correctAnswer: { kind: 'GENERIC_INTEGER', value: Math.floor(random() * 5) },
        settledAt: daysFromNow(spec.startInDays + 1),
        note: null,
      });
    }
  }

  return outcomes;
}

function predictionFor(
  question: Question,
  build: DrawBuild | undefined,
  random: () => number,
  cache: Map<string, readonly PlayerId[]>,
): PredictionPayload | null {
  if (question.family === 'TYPED' && build !== undefined) {
    const sectionPicks = cache.get(build.draw.id) ?? (() => {
      const picks = [...build.bySection]
        .sort((a, b) => a[0] - b[0])
        .map(([, entries]) => {
          // Two thirds of the time a participant backs one of the section's
          // seeds; the rest of the time they take a flyer.
          const seeds = entries.filter((e) => e.seed !== null);
          const from = random() < 0.66 && seeds.length > 0 ? seeds : entries;
          return (from[Math.floor(random() * from.length)] ?? entries[0])?.playerId ?? '';
        })
        .filter((pid) => pid !== '');
      cache.set(build.draw.id, picks);
      return picks;
    })();

    switch (question.kind) {
      case 'QF_PICKS':
        return {
          kind: 'QF_PICKS',
          picks: sectionPicks.map((playerId, index) => ({ sectionIndex: index + 1, playerId })),
        };
      case 'SF_PICKS':
        return { kind: 'SF_PICKS', playerIds: shuffle(random, sectionPicks).slice(0, 4) };
      case 'FINALIST_PICKS':
        return { kind: 'FINALIST_PICKS', playerIds: shuffle(random, sectionPicks).slice(0, 2) };
      case 'CHAMPION': {
        const playerId = shuffle(random, sectionPicks)[0];
        return playerId === undefined ? null : { kind: 'CHAMPION', playerId };
      }
      case 'UNDERPERFORMER': {
        const eligible = build.entries.filter((e) => e.seed !== null && e.seed <= 10);
        const entry = eligible[Math.floor(random() * eligible.length)];
        return entry === undefined ? null : { kind: 'UNDERPERFORMER', playerId: entry.playerId };
      }
      case 'BREAKOUT': {
        const eligible = build.entries.filter((e) => e.seed === null);
        const entry = eligible[Math.floor(random() * eligible.length)];
        return entry === undefined ? null : { kind: 'BREAKOUT', playerId: entry.playerId };
      }
      default:
        return null;
    }
  }

  if (question.answerType === 'MATCH_RESULT' && question.matchup !== null) {
    const format = build?.draw.bestOf ?? 3;
    const legal: readonly SetScore[] = format === 5 ? ['3-0', '3-1', '3-2'] : ['2-0', '2-1'];
    const setScore = legal[Math.floor(random() * legal.length)];
    if (setScore === undefined) {
      return null;
    }
    return {
      kind: 'GENERIC_MATCH_RESULT',
      winnerId: question.matchup[random() < 0.5 ? 0 : 1],
      setScore,
    };
  }

  if (question.answerType === 'INTEGER') {
    return { kind: 'GENERIC_INTEGER', value: Math.floor(random() * 5) };
  }

  return null;
}

export function buildGame(spec: GameSpec): BuiltGame {
  const builds = spec.draws.map((drawSpec, index) => buildDraw(spec, drawSpec, index * 101));
  const buildByDraw = new Map(builds.map((b) => [b.draw.id, b]));

  const tournament: Tournament = {
    id: spec.key,
    name: spec.name,
    category: spec.category,
    surface: spec.surface,
    location: spec.location,
    startDate: dateOnly(daysFromNow(spec.startInDays)),
    endDate: dateOnly(daysFromNow(spec.endInDays)),
    signupDeadline: daysFromNow(spec.signupDeadlineInDays),
    visibility: spec.visibility,
    joinCode: spec.joinCode,
    status: spec.status,
    rulesMarkdown: spec.rulesMarkdown,
    scoringProfile: DEFAULT_SCORING_PROFILE,
    createdAt: daysFromNow(spec.startInDays - 60),
  };

  const participations: Participation[] = spec.participants.map((user, index) => ({
    id: id(spec.key, 'part', index + 1),
    userId: user.id,
    tournamentId: spec.key,
    joinedAt: daysFromNow(spec.signupDeadlineInDays - 7),
    status: 'ACTIVE',
  }));

  const plans = planGroups(spec);
  const questions = buildQuestions(spec, plans, builds);
  const questionOutcomes = buildQuestionOutcomes(spec, plans, questions, builds);
  const outcomeByQuestion = new Map(questionOutcomes.map((o) => [o.questionId, o]));
  const planByGroup = new Map(plans.map((p) => [p.group.id, p]));

  // The outcome grid, flattened across draws.
  const outcomes: OutcomeEntry[] = builds.flatMap((build) =>
    [...build.outcomes].map(([playerId, roundReached]) => ({
      drawId: build.draw.id,
      playerId,
      roundReached,
      note: null,
    })),
  );
  const outcomeByPlayer = new Map(outcomes.map((o) => [o.playerId, o.roundReached]));

  const playerNames = new Map(ALL_PLAYERS.map((p) => [p.id, p.fullName]));
  const nameOf = (playerId: PlayerId): string => playerNames.get(playerId) ?? playerId;

  const predictions: Prediction[] = [];
  const scores: ScoreEntry[] = [];

  participations.forEach((participation, participantIndex) => {
    const random = createRandom(spec.randomSeed + (participantIndex + 1) * 7919);
    const sectionCache = new Map<string, readonly PlayerId[]>();

    for (const question of questions) {
      const plan = planByGroup.get(question.betGroupId);
      if (plan === undefined || plan.group.status === 'DRAFT') {
        continue;
      }
      // The fixture's own player leaves one question of the open group blank,
      // so the betting screen has a genuine half-finished draft to render.
      const leaveBlank =
        participantIndex === 0 && plan.open && question.answerType === 'MATCH_RESULT'
        && question.drawId === builds[builds.length - 1]?.draw.id;
      if (leaveBlank) {
        continue;
      }

      const build = question.drawId === null ? undefined : buildByDraw.get(question.drawId);
      const payload = predictionFor(question, build, random, sectionCache);
      if (payload === null) {
        continue;
      }

      predictions.push({
        id: id(participation.id, question.id),
        participationId: participation.id,
        questionId: question.id,
        payload,
        submittedAt: plan.open ? null : daysFromNow(spec.startInDays - 1),
        updatedAt: daysFromNow(spec.startInDays - 1),
      });

      if (!plan.settled) {
        continue;
      }
      const score = scorePrediction(
        payload,
        outcomeByQuestion.get(question.id)?.correctAnswer ?? null,
        outcomeByPlayer,
        tournament.scoringProfile,
        nameOf,
      );
      if (score !== null) {
        scores.push({
          id: id(participation.id, question.id, 'score'),
          participationId: participation.id,
          questionId: question.id,
          points: score.points,
          reason: score.reason,
          calculatedAt: daysFromNow(spec.startInDays + settledRounds(spec.stage)),
        });
      }
    }
  });

  return {
    tournament,
    draws: builds.map((b) => b.draw),
    sections: builds.flatMap((b) => b.sections),
    entries: builds.flatMap((b) => b.entries),
    outcomes,
    participations,
    betGroups: plans.map((p) => p.group),
    questions,
    questionOutcomes,
    predictions,
    scores,
  };
}
