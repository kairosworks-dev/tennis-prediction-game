import type {
  BetGroup, Draw, DrawEntry, DrawSection, OutcomeEntry, Participation, Player,
  Prediction, Question, QuestionOutcome, ScoreEntry, Tournament, User, UserId,
} from '../../types';
import { ALL_PLAYERS } from './players';
import { buildGame, type BuiltGame, type GameSpec } from './buildGame';
import { daysFromNow, id } from './seed';

/** The signed-in participant the fixtures are written from. */
export const CURRENT_USER_ID: UserId = 'user-1';
export const ADMIN_USER_ID: UserId = 'user-admin';

function participant(index: number, displayName: string, fullName: string | null): User {
  return {
    id: id('user', index),
    email: `${displayName.toLowerCase().replace(/[^a-z]/g, '')}@example.com`,
    displayName,
    fullName,
    isAdmin: false,
    isActive: true,
    emailVerifiedAt: daysFromNow(-200),
    createdAt: daysFromNow(-240),
  };
}

const ADMIN: User = {
  id: ADMIN_USER_ID,
  email: 'organiser@example.com',
  displayName: 'The organiser',
  fullName: 'Hélène Moreau',
  isAdmin: true,
  isActive: true,
  emailVerifiedAt: daysFromNow(-400),
  createdAt: daysFromNow(-400),
};

/** Fourteen players, the first of whom is the fixture's own account. */
const PARTICIPANTS: readonly User[] = [
  participant(1, 'You', 'Mattia Ricci'),
  participant(2, 'Sofia', 'Sofia Lindqvist'),
  participant(3, 'Jonas', 'Jonas Brandt'),
  participant(4, 'Priya', 'Priya Raman'),
  participant(5, 'Tomás', 'Tomás Almeida'),
  participant(6, 'Anneke', 'Anneke de Vries'),
  participant(7, 'Marek', 'Marek Dvorak'),
  participant(8, 'Yusuf', 'Yusuf Demir'),
  participant(9, 'Claire', 'Claire Fontaine'),
  participant(10, 'Bea', 'Beatriz Pereira'),
  participant(11, 'Sam', 'Sam Okonkwo'),
  participant(12, 'Lena', 'Lena Hofer'),
  participant(13, 'Rui', 'Rui Tavares'),
  participant(14, 'Ada', 'Ada Kowalski'),
];

const ALL_USERS: readonly User[] = [ADMIN, ...PARTICIPANTS];

const GRAND_SLAM_RULES = `
Deadlines are the deadlines. If a group closes while you are asleep, that is
between you and your alarm clock.

Withdrawals and retirements are settled by whoever is running the game, and the
reasoning shows up next to your points.

Nobody sees anybody else's picks until the group locks.
`.trim();

const GAME_SPECS: readonly GameSpec[] = [
  {
    // Mid-tournament, two draws — the state most of the app is designed around.
    key: 'roland-garros-2026',
    name: 'Roland-Garros 2026',
    category: 'GRAND_SLAM',
    surface: 'CLAY',
    location: 'Paris, France',
    startInDays: -10,
    endInDays: 4,
    signupDeadlineInDays: -11,
    status: 'RUNNING',
    visibility: 'PUBLIC',
    joinCode: null,
    rulesMarkdown: GRAND_SLAM_RULES,
    draws: [
      { tour: 'ATP', bestOf: 5, officialDrawUrl: 'https://www.rolandgarros.com/en-us/draws' },
      { tour: 'WTA', bestOf: 3, officialDrawUrl: 'https://www.rolandgarros.com/en-us/draws' },
    ],
    stage: 'QUARTER_FINALS',
    participants: PARTICIPANTS,
    randomSeed: 20260525,
  },
  {
    // Finished and read-only.
    key: 'australian-open-2026',
    name: 'Australian Open 2026',
    category: 'GRAND_SLAM',
    surface: 'HARD',
    location: 'Melbourne, Australia',
    startInDays: -240,
    endInDays: -227,
    signupDeadlineInDays: -241,
    status: 'FINISHED',
    visibility: 'PUBLIC',
    joinCode: null,
    rulesMarkdown: GRAND_SLAM_RULES,
    draws: [
      { tour: 'ATP', bestOf: 5, officialDrawUrl: null },
      { tour: 'WTA', bestOf: 3, officialDrawUrl: null },
    ],
    stage: 'COMPLETE',
    participants: PARTICIPANTS.slice(0, 12),
    randomSeed: 20260112,
  },
  {
    // Open for signup. The fixture's own account has deliberately not joined,
    // so the game list has a live Join action to render.
    key: 'wimbledon-2026',
    name: 'Wimbledon 2026',
    category: 'GRAND_SLAM',
    surface: 'GRASS',
    location: 'London, United Kingdom',
    startInDays: 25,
    endInDays: 38,
    signupDeadlineInDays: 18,
    status: 'PUBLISHED',
    visibility: 'PUBLIC',
    joinCode: null,
    rulesMarkdown: GRAND_SLAM_RULES,
    draws: [
      { tour: 'ATP', bestOf: 5, officialDrawUrl: null },
      { tour: 'WTA', bestOf: 3, officialDrawUrl: null },
    ],
    stage: 'NOT_STARTED',
    participants: PARTICIPANTS.slice(1, 7),
    randomSeed: 20260629,
  },
  {
    // A one-draw, private game — covers the join-code path (decision D4) and a
    // tour-level event, where a game has a single draw rather than two.
    key: 'monte-carlo-2026',
    name: 'Monte-Carlo Masters 2026',
    category: 'ATP',
    surface: 'CLAY',
    location: 'Monaco',
    startInDays: 12,
    endInDays: 19,
    signupDeadlineInDays: 9,
    status: 'PUBLISHED',
    visibility: 'PRIVATE',
    joinCode: 'ROLEX26',
    rulesMarkdown: 'Same rules as the slams, one draw only.',
    draws: [{ tour: 'ATP', bestOf: 3, officialDrawUrl: null }],
    stage: 'NOT_STARTED',
    participants: PARTICIPANTS.slice(2, 6),
    randomSeed: 20260412,
  },
];

/**
 * Everything `MockApiClient` reads and writes. Built fresh on every call so
 * each test gets its own copy and mutations in one test cannot leak into
 * another.
 */
export interface MockDatabase {
  users: User[];
  players: Player[];
  tournaments: Tournament[];
  draws: Draw[];
  sections: DrawSection[];
  entries: DrawEntry[];
  participations: Participation[];
  betGroups: BetGroup[];
  questions: Question[];
  questionOutcomes: QuestionOutcome[];
  predictions: Prediction[];
  outcomes: OutcomeEntry[];
  scores: ScoreEntry[];
  /** Null when nobody is signed in. */
  sessionUserId: UserId | null;
  /** Tokens handed out by the fixture, keyed by token. */
  verificationTokens: Map<string, UserId>;
  passwordResetTokens: Map<string, UserId>;
}

export interface CreateDatabaseOptions {
  /** Start signed out, to exercise the landing page and the auth flow. */
  readonly signedIn?: boolean;
  /** Start as the organiser rather than a participant. */
  readonly asAdmin?: boolean;
}

export function createDatabase(options: CreateDatabaseOptions = {}): MockDatabase {
  const games: readonly BuiltGame[] = GAME_SPECS.map(buildGame);
  const signedIn = options.signedIn ?? true;
  const asAdmin = options.asAdmin ?? false;

  return {
    users: [...ALL_USERS],
    players: [...ALL_PLAYERS],
    tournaments: games.map((g) => g.tournament),
    draws: games.flatMap((g) => [...g.draws]),
    sections: games.flatMap((g) => [...g.sections]),
    entries: games.flatMap((g) => [...g.entries]),
    participations: games.flatMap((g) => [...g.participations]),
    betGroups: games.flatMap((g) => [...g.betGroups]),
    questions: games.flatMap((g) => [...g.questions]),
    questionOutcomes: games.flatMap((g) => [...g.questionOutcomes]),
    predictions: games.flatMap((g) => [...g.predictions]),
    outcomes: games.flatMap((g) => [...g.outcomes]),
    scores: games.flatMap((g) => [...g.scores]),
    sessionUserId: signedIn ? (asAdmin ? ADMIN_USER_ID : CURRENT_USER_ID) : null,
    verificationTokens: new Map(),
    passwordResetTokens: new Map(),
  };
}

export { DEFAULT_SCORING_PROFILE } from './buildGame';
