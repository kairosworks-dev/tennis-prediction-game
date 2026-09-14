import type { ApiClient } from '../apiClient';
import type {
  AuthenticatedUser, BetGroup, BetGroupScoreBlock, CreateBetGroupRequest,
  CreateDrawRequest, CreatePlayerRequest, CreateQuestionRequest,
  CreateTournamentRequest, Draw, DrawId, DrawSectionWithEntries, GameListState,
  JoinTournamentRequest, ListPlayersQuery, ListUsersQuery, LoginRequest,
  NextGameTeaser, Paginated, ParticipantPrediction, Participation,
  PasswordResetConfirmRequest, PasswordResetRequest, Player, Prediction,
  PutDrawEntriesRequest, PutDrawOutcomesRequest, PutPredictionRequest,
  PutQuestionOutcomeRequest, Question, QuestionId, QuestionScoreRow,
  RankingEntry, RecalculateResult, RegisterRequest, ScoreBreakdown,
  TournamentDetail, TournamentId, TournamentSummary, TypedQuestionKind,
  UpdateBetGroupRequest, UpdateProfileRequest, UpdateQuestionRequest,
  UpdateTournamentRequest, UpdateUserRequest, User, VerifyEmailRequest,
  BetGroupId, PredictionPayload, BetGroupPoints,
} from '../types';
import { conflict, forbidden, notFound, unauthorized, validationFailed } from '../errors';
import { createDatabase, type CreateDatabaseOptions, type MockDatabase } from './fixtures';
import { expectedPayloadKind, validatePrediction, type ValidationContext } from './validation';

export interface MockApiClientOptions extends CreateDatabaseOptions {
  /** Artificial latency in milliseconds. Set to 0 in tests. */
  readonly latencyMs?: number;
}

/**
 * An in-memory stand-in for the backend (spec 7.2, step 1).
 *
 * It holds the fixture database, enforces the validation and authorisation
 * rules the real API will enforce, and rejects with the same RFC 7807 problem
 * shape. That is the point: the application talks to this the same way it will
 * talk to `HttpApiClient`, so step 3 is a change of environment variable.
 */
export class MockApiClient implements ApiClient {
  private readonly db: MockDatabase;
  private readonly latencyMs: number;
  private nextId = 1;

  constructor(options: MockApiClientOptions = {}) {
    this.db = createDatabase(options);
    this.latencyMs = options.latencyMs ?? 180;
  }

  /** Test seam: inspect or arrange fixture state directly. */
  get database(): MockDatabase {
    return this.db;
  }

  /* --- plumbing --- */

  private async delay<T>(value: T): Promise<T> {
    if (this.latencyMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, this.latencyMs));
    }
    return value;
  }

  private generateId(prefix: string): string {
    this.nextId += 1;
    return `${prefix}-${String(this.nextId)}`;
  }

  private currentUser(): User {
    const userId = this.db.sessionUserId;
    const user = userId === null ? undefined : this.db.users.find((u) => u.id === userId);
    if (user === undefined) {
      throw unauthorized();
    }
    return user;
  }

  private requireAdmin(): User {
    const user = this.currentUser();
    if (!user.isAdmin) {
      throw forbidden('That is an organiser action.');
    }
    return user;
  }

  private tournamentOrThrow(tournamentId: TournamentId) {
    const tournament = this.db.tournaments.find((t) => t.id === tournamentId);
    if (tournament === undefined) {
      throw notFound('That game');
    }
    return tournament;
  }

  private participationFor(tournamentId: TournamentId, userId: string): Participation | null {
    return (
      this.db.participations.find((p) => p.tournamentId === tournamentId && p.userId === userId) ??
      null
    );
  }

  private requireParticipation(tournamentId: TournamentId): Participation {
    const user = this.currentUser();
    const participation = this.participationFor(tournamentId, user.id);
    if (participation === null) {
      throw forbidden('You have not joined this game.');
    }
    return participation;
  }

  private groupOrThrow(betGroupId: BetGroupId): BetGroup {
    const group = this.db.betGroups.find((g) => g.id === betGroupId);
    if (group === undefined) {
      throw notFound('That bet group');
    }
    return group;
  }

  private questionOrThrow(questionId: QuestionId): Question {
    const question = this.db.questions.find((q) => q.id === questionId);
    if (question === undefined) {
      throw notFound('That question');
    }
    return question;
  }

  /* --- authentication and account --- */

  async register(request: RegisterRequest): Promise<AuthenticatedUser> {
    const email = request.email.trim().toLowerCase();
    if (!email.includes('@')) {
      throw validationFailed('That does not look like an email address.', { email: ['Enter a valid address.'] });
    }
    if (request.password.length < 10) {
      throw validationFailed('Passwords need at least ten characters.', {
        password: ['Too short.'],
      });
    }
    if (request.displayName.trim().length < 2) {
      throw validationFailed('Display names need at least two characters.', {
        displayName: ['Too short.'],
      });
    }
    if (this.db.users.some((u) => u.email.toLowerCase() === email)) {
      throw conflict('An account already exists for that address.');
    }

    const user: User = {
      id: this.generateId('user'),
      email,
      displayName: request.displayName.trim(),
      fullName: null,
      isAdmin: false,
      isActive: true,
      emailVerifiedAt: null,
      createdAt: new Date().toISOString(),
    };
    this.db.users.push(user);
    this.db.sessionUserId = user.id;
    // The console mock stands in for transactional email (decision D8).
    this.db.verificationTokens.set(`verify-${user.id}`, user.id);
    return this.delay({ user, requiresEmailVerification: true });
  }

  async login(request: LoginRequest): Promise<AuthenticatedUser> {
    const user = this.db.users.find((u) => u.email.toLowerCase() === request.email.trim().toLowerCase());
    if (user === undefined || request.password.length === 0) {
      throw validationFailed('That email and password do not match an account.');
    }
    if (!user.isActive) {
      throw forbidden('That account has been deactivated.');
    }
    this.db.sessionUserId = user.id;
    return this.delay({ user, requiresEmailVerification: user.emailVerifiedAt === null });
  }

  async logout(): Promise<void> {
    this.db.sessionUserId = null;
    return this.delay(undefined);
  }

  async verifyEmail(request: VerifyEmailRequest): Promise<AuthenticatedUser> {
    const userId = this.db.verificationTokens.get(request.token);
    const index = this.db.users.findIndex((u) => u.id === userId);
    if (userId === undefined || index < 0) {
      throw validationFailed('That verification link is not valid any more.');
    }
    const existing = this.db.users[index];
    if (existing === undefined) {
      throw notFound('That account');
    }
    const user: User = { ...existing, emailVerifiedAt: new Date().toISOString() };
    this.db.users[index] = user;
    this.db.verificationTokens.delete(request.token);
    return this.delay({ user, requiresEmailVerification: false });
  }

  async requestPasswordReset(request: PasswordResetRequest): Promise<void> {
    const user = this.db.users.find((u) => u.email.toLowerCase() === request.email.trim().toLowerCase());
    if (user !== undefined) {
      this.db.passwordResetTokens.set(`reset-${user.id}`, user.id);
    }
    // Always resolves, so the response does not reveal whether an account exists.
    return this.delay(undefined);
  }

  async confirmPasswordReset(request: PasswordResetConfirmRequest): Promise<void> {
    if (!this.db.passwordResetTokens.has(request.token)) {
      throw validationFailed('That reset link is not valid any more.');
    }
    if (request.password.length < 10) {
      throw validationFailed('Passwords need at least ten characters.', { password: ['Too short.'] });
    }
    this.db.passwordResetTokens.delete(request.token);
    return this.delay(undefined);
  }

  async getCurrentUser(): Promise<User | null> {
    const userId = this.db.sessionUserId;
    return this.delay(userId === null ? null : (this.db.users.find((u) => u.id === userId) ?? null));
  }

  async updateCurrentUser(request: UpdateProfileRequest): Promise<User> {
    const current = this.currentUser();
    const index = this.db.users.findIndex((u) => u.id === current.id);
    const emailChanged = request.email !== undefined && request.email !== current.email;
    const user: User = {
      ...current,
      ...(request.displayName === undefined ? {} : { displayName: request.displayName }),
      ...(request.fullName === undefined ? {} : { fullName: request.fullName }),
      ...(request.email === undefined ? {} : { email: request.email }),
      // Changing the address costs you your verification (spec 4.2).
      ...(emailChanged ? { emailVerifiedAt: null } : {}),
    };
    this.db.users[index] = user;
    return this.delay(user);
  }

  async deleteCurrentUser(): Promise<void> {
    const current = this.currentUser();
    const index = this.db.users.findIndex((u) => u.id === current.id);
    // Anonymise rather than cascade, so past leaderboards stay coherent.
    this.db.users[index] = {
      ...current,
      email: `deleted-${current.id}@example.invalid`,
      displayName: 'Former participant',
      fullName: null,
      isActive: false,
    };
    this.db.sessionUserId = null;
    return this.delay(undefined);
  }

  /* --- landing page --- */

  async getNextGame(): Promise<NextGameTeaser | null> {
    const now = Date.now();
    const open = this.db.tournaments
      .filter((t) => t.status === 'PUBLISHED' && Date.parse(t.signupDeadline) > now)
      .filter((t) => t.visibility === 'PUBLIC')
      .sort((a, b) => Date.parse(a.signupDeadline) - Date.parse(b.signupDeadline));
    const next = open[0];
    if (next === undefined) {
      return this.delay(null);
    }
    return this.delay({
      tournamentId: next.id,
      name: next.name,
      category: next.category,
      surface: next.surface,
      location: next.location,
      startDate: next.startDate,
      endDate: next.endDate,
      signupDeadline: next.signupDeadline,
      participantCount: this.db.participations.filter((p) => p.tournamentId === next.id).length,
    });
  }

  /* --- game selection --- */

  async listTournaments(): Promise<readonly TournamentSummary[]> {
    const user = this.currentUser();
    const now = Date.now();

    const visible = this.db.tournaments.filter((t) => {
      if (t.status === 'DRAFT') {
        return user.isAdmin;
      }
      if (t.visibility === 'PRIVATE') {
        return this.participationFor(t.id, user.id) !== null;
      }
      return true;
    });

    const summaries = visible.map((tournament): TournamentSummary => {
      const participation = this.participationFor(tournament.id, user.id);
      const participantCount = this.db.participations.filter((p) => p.tournamentId === tournament.id).length;
      const groups = this.db.betGroups
        .filter((g) => g.tournamentId === tournament.id)
        .sort((a, b) => Date.parse(a.deadline) - Date.parse(b.deadline));
      const openGroup = groups.find((g) => g.status === 'OPEN');

      const state: GameListState =
        tournament.status === 'FINISHED'
          ? 'FINISHED'
          : participation !== null && tournament.status === 'RUNNING'
            ? 'RUNNING'
            : Date.parse(tournament.signupDeadline) > now
              ? 'OPEN_FOR_SIGNUP'
              : 'RUNNING';

      const ranking = participation === null ? [] : this.rankingFor(tournament.id);
      const own = ranking.find((r) => r.participationId === participation?.id);

      return {
        tournament,
        state,
        participantCount,
        participationId: participation?.id ?? null,
        nextDeadline: openGroup?.deadline ?? null,
        userPosition: own?.position ?? null,
        userPoints: own?.totalPoints ?? null,
        currentRound: openGroup?.round ?? null,
      };
    });

    return this.delay(summaries);
  }

  async getTournament(tournamentId: TournamentId): Promise<TournamentDetail> {
    const user = this.currentUser();
    const tournament = this.tournamentOrThrow(tournamentId);
    const participation = this.participationFor(tournamentId, user.id);
    if (tournament.visibility === 'PRIVATE' && participation === null && !user.isAdmin) {
      throw notFound('That game');
    }
    return this.delay({
      // The join code is an organiser's to hand out, not a participant's to read.
      tournament: user.isAdmin ? tournament : { ...tournament, joinCode: null },
      draws: this.db.draws.filter((d) => d.tournamentId === tournamentId),
      participantCount: this.db.participations.filter((p) => p.tournamentId === tournamentId).length,
      participationId: participation?.id ?? null,
    });
  }

  async joinTournament(request: JoinTournamentRequest): Promise<Participation> {
    const user = this.currentUser();
    const tournament = this.tournamentOrThrow(request.tournamentId);

    if (user.emailVerifiedAt === null) {
      throw forbidden('Confirm your email address before joining a game.');
    }
    if (Date.parse(tournament.signupDeadline) <= Date.now()) {
      throw forbidden('Signup for that game has closed.');
    }
    if (tournament.visibility === 'PRIVATE' && request.joinCode !== tournament.joinCode) {
      throw validationFailed('That join code is not right.', { joinCode: ['Check it with the organiser.'] });
    }
    if (this.participationFor(tournament.id, user.id) !== null) {
      throw conflict('You have already joined this game.');
    }

    const participation: Participation = {
      id: this.generateId('part'),
      userId: user.id,
      tournamentId: tournament.id,
      joinedAt: new Date().toISOString(),
      status: 'ACTIVE',
    };
    this.db.participations.push(participation);
    return this.delay(participation);
  }

  /* --- inside a game --- */

  async listDraws(tournamentId: TournamentId): Promise<readonly Draw[]> {
    this.tournamentOrThrow(tournamentId);
    return this.delay(this.db.draws.filter((d) => d.tournamentId === tournamentId));
  }

  async listDrawEntries(
    tournamentId: TournamentId,
    drawId: DrawId,
  ): Promise<readonly DrawSectionWithEntries[]> {
    this.tournamentOrThrow(tournamentId);
    return this.delay(this.sectionsWithEntries(drawId));
  }

  private sectionsWithEntries(drawId: DrawId): readonly DrawSectionWithEntries[] {
    const draw = this.db.draws.find((d) => d.id === drawId);
    if (draw === undefined) {
      throw notFound('That draw');
    }
    const outcomeByPlayer = new Map(
      this.db.outcomes.filter((o) => o.drawId === drawId).map((o) => [o.playerId, o.roundReached]),
    );
    return this.db.sections
      .filter((s) => s.drawId === drawId)
      .sort((a, b) => a.index - b.index)
      .map((section) => ({
        section,
        entries: this.db.entries
          .filter((e) => e.sectionId === section.id)
          .map((entry) => {
            const player = this.db.players.find((p) => p.id === entry.playerId);
            if (player === undefined) {
              throw notFound('A player in this draw');
            }
            return { entry, player, roundReached: outcomeByPlayer.get(entry.playerId) ?? null };
          })
          .sort((a, b) => (a.entry.seed ?? 999) - (b.entry.seed ?? 999)),
      }));
  }

  async listBetGroups(tournamentId: TournamentId): Promise<readonly BetGroup[]> {
    const user = this.currentUser();
    this.tournamentOrThrow(tournamentId);
    return this.delay(
      this.db.betGroups
        .filter((g) => g.tournamentId === tournamentId)
        // A draft group is the organiser's work in progress.
        .filter((g) => g.status !== 'DRAFT' || user.isAdmin)
        .sort((a, b) => Date.parse(a.deadline) - Date.parse(b.deadline)),
    );
  }

  async listQuestions(
    tournamentId: TournamentId,
    betGroupId: BetGroupId,
  ): Promise<readonly Question[]> {
    this.tournamentOrThrow(tournamentId);
    const group = this.groupOrThrow(betGroupId);
    if (group.tournamentId !== tournamentId) {
      throw notFound('That bet group');
    }
    return this.delay(
      this.db.questions.filter((q) => q.betGroupId === betGroupId).sort((a, b) => a.position - b.position),
    );
  }

  async listOwnPredictions(tournamentId: TournamentId): Promise<readonly Prediction[]> {
    const participation = this.requireParticipation(tournamentId);
    const questionIds = new Set(this.questionIdsFor(tournamentId));
    return this.delay(
      this.db.predictions.filter(
        (p) => p.participationId === participation.id && questionIds.has(p.questionId),
      ),
    );
  }

  private questionIdsFor(tournamentId: TournamentId): readonly QuestionId[] {
    const groupIds = new Set(
      this.db.betGroups.filter((g) => g.tournamentId === tournamentId).map((g) => g.id),
    );
    return this.db.questions.filter((q) => groupIds.has(q.betGroupId)).map((q) => q.id);
  }

  async listQuestionPredictions(
    tournamentId: TournamentId,
    questionId: QuestionId,
  ): Promise<readonly ParticipantPrediction[]> {
    this.requireParticipation(tournamentId);
    const question = this.questionOrThrow(questionId);
    const group = this.groupOrThrow(question.betGroupId);
    if (group.status === 'OPEN' || group.status === 'DRAFT') {
      throw forbidden("Everyone's picks open when the group locks.");
    }

    const rows = this.db.participations
      .filter((p) => p.tournamentId === tournamentId)
      .map((participation): ParticipantPrediction => {
        const user = this.db.users.find((u) => u.id === participation.userId);
        const prediction = this.db.predictions.find(
          (p) => p.participationId === participation.id && p.questionId === questionId,
        );
        return {
          participationId: participation.id,
          displayName: user?.displayName ?? 'Former participant',
          payload: prediction?.payload ?? null,
        };
      });
    return this.delay(rows);
  }

  async putPrediction(request: PutPredictionRequest): Promise<Prediction> {
    const participation = this.requireParticipation(request.tournamentId);
    const question = this.questionOrThrow(request.questionId);
    const group = this.groupOrThrow(question.betGroupId);

    if (group.tournamentId !== request.tournamentId) {
      throw notFound('That question');
    }
    // Spec 5.3: the question's bet group must be open.
    if (group.status !== 'OPEN') {
      throw forbidden(
        group.status === 'DRAFT'
          ? 'That group is not open yet.'
          : 'That group has closed. Predictions are final.',
      );
    }
    const expected = expectedPayloadKind(question);
    if (request.payload.kind !== expected) {
      throw validationFailed(`This question expects a ${expected} answer.`);
    }

    // A draft saves the shape without holding it to the cross-question rules.
    if (!request.asDraft) {
      validatePrediction(request.payload, this.validationContextFor(question, participation.id));
    }

    const existingIndex = this.db.predictions.findIndex(
      (p) => p.participationId === participation.id && p.questionId === question.id,
    );
    const now = new Date().toISOString();
    const prediction: Prediction = {
      id: this.db.predictions[existingIndex]?.id ?? this.generateId('pred'),
      participationId: participation.id,
      questionId: question.id,
      payload: request.payload,
      submittedAt: request.asDraft ? null : now,
      updatedAt: now,
    };
    if (existingIndex >= 0) {
      this.db.predictions[existingIndex] = prediction;
    } else {
      this.db.predictions.push(prediction);
    }
    return this.delay(prediction);
  }

  private validationContextFor(question: Question, participationId: string): ValidationContext {
    const questionsInGroup = this.db.questions.filter((q) => q.betGroupId === question.betGroupId);
    // Cross-question rules only compare answers within the same draw.
    const siblings = questionsInGroup.filter((q) => q.drawId === question.drawId && q.kind !== null);

    const siblingPayloads = new Map<TypedQuestionKind, PredictionPayload>();
    const questionIdByKind = new Map<TypedQuestionKind, QuestionId>();
    for (const sibling of siblings) {
      if (sibling.kind === null) {
        continue;
      }
      questionIdByKind.set(sibling.kind, sibling.id);
      const prediction = this.db.predictions.find(
        (p) => p.participationId === participationId && p.questionId === sibling.id,
      );
      if (prediction !== undefined) {
        siblingPayloads.set(sibling.kind, prediction.payload);
      }
    }

    const draw = question.drawId === null ? null : (this.db.draws.find((d) => d.id === question.drawId) ?? null);
    return {
      question,
      draw,
      entries: question.drawId === null ? [] : this.db.entries.filter((e) => e.drawId === question.drawId),
      siblingPayloads,
      questionsInGroup,
      questionIdByKind,
    };
  }

  async getScoreBreakdown(tournamentId: TournamentId): Promise<ScoreBreakdown> {
    const participation = this.requireParticipation(tournamentId);
    const groups = this.db.betGroups
      .filter((g) => g.tournamentId === tournamentId && g.status !== 'DRAFT')
      .sort((a, b) => Date.parse(a.deadline) - Date.parse(b.deadline));

    const blocks = groups.map((betGroup): BetGroupScoreBlock => {
      const rows = this.db.questions
        .filter((q) => q.betGroupId === betGroup.id)
        .sort((a, b) => a.position - b.position)
        .map((question): QuestionScoreRow => {
          const prediction = this.db.predictions.find(
            (p) => p.participationId === participation.id && p.questionId === question.id,
          );
          const score = this.db.scores.find(
            (s) => s.participationId === participation.id && s.questionId === question.id,
          );
          const outcome = this.db.questionOutcomes.find((o) => o.questionId === question.id);
          return {
            question,
            ownPayload: prediction?.payload ?? null,
            correctAnswer: outcome?.correctAnswer ?? null,
            points: score?.points ?? null,
            reason: score?.reason ?? null,
          };
        });
      return {
        betGroup,
        rows,
        subtotal: rows.reduce((sum, row) => sum + (row.points ?? 0), 0),
        comparisonAvailable: betGroup.status === 'LOCKED' || betGroup.status === 'SETTLED',
      };
    });

    const ranking = this.rankingFor(tournamentId);
    const own = ranking.find((r) => r.participationId === participation.id);
    return this.delay({
      tournamentId,
      total: blocks.reduce((sum, block) => sum + block.subtotal, 0),
      position: own?.position ?? null,
      participantCount: this.db.participations.filter((p) => p.tournamentId === tournamentId).length,
      groups: blocks,
    });
  }

  async getRanking(tournamentId: TournamentId): Promise<readonly RankingEntry[]> {
    this.tournamentOrThrow(tournamentId);
    return this.delay(this.rankingFor(tournamentId));
  }

  /**
   * Reads persisted score entries — it never recomputes them (spec 5.4). Ties
   * share a position and the next position skips (decision D13).
   */
  private rankingFor(tournamentId: TournamentId): readonly RankingEntry[] {
    const participations = this.db.participations.filter((p) => p.tournamentId === tournamentId);
    const settled = this.db.betGroups
      .filter((g) => g.tournamentId === tournamentId && g.status === 'SETTLED')
      .sort((a, b) => Date.parse(a.deadline) - Date.parse(b.deadline));
    const lastGroup = settled[settled.length - 1];
    const questionIdsByGroup = new Map(
      settled.map((g) => [g.id, new Set(this.db.questions.filter((q) => q.betGroupId === g.id).map((q) => q.id))]),
    );

    const rows = participations.map((participation) => {
      const own = this.db.scores.filter((s) => s.participationId === participation.id);
      const perGroupPoints: BetGroupPoints[] = settled.map((group) => {
        const ids = questionIdsByGroup.get(group.id) ?? new Set<string>();
        return {
          betGroupId: group.id,
          title: group.title,
          points: own.filter((s) => ids.has(s.questionId)).reduce((sum, s) => sum + s.points, 0),
        };
      });
      const user = this.db.users.find((u) => u.id === participation.userId);
      return {
        participationId: participation.id,
        displayName: user?.displayName ?? 'Former participant',
        isCurrentUser: participation.userId === this.db.sessionUserId,
        totalPoints: perGroupPoints.reduce((sum, g) => sum + g.points, 0),
        lastGroupPoints:
          lastGroup === undefined
            ? 0
            : (perGroupPoints.find((g) => g.betGroupId === lastGroup.id)?.points ?? 0),
        perGroupPoints,
      };
    });

    rows.sort((a, b) => b.totalPoints - a.totalPoints || a.displayName.localeCompare(b.displayName));

    const previousTotals = new Map(
      rows.map((r) => [r.participationId, r.totalPoints - r.lastGroupPoints] as const),
    );
    const previousOrder = [...rows]
      .sort(
        (a, b) =>
          (previousTotals.get(b.participationId) ?? 0) - (previousTotals.get(a.participationId) ?? 0) ||
          a.displayName.localeCompare(b.displayName),
      )
      .map((r) => r.participationId);

    let position = 0;
    let previousPoints: number | null = null;
    return rows.map((row, index): RankingEntry => {
      if (previousPoints === null || row.totalPoints !== previousPoints) {
        position = index + 1;
        previousPoints = row.totalPoints;
      }
      const wasAt = previousOrder.indexOf(row.participationId);
      return {
        ...row,
        position,
        movement: settled.length < 2 ? null : wasAt - index,
      };
    });
  }

  /* --- admin --- */

  async listUsers(query: ListUsersQuery): Promise<Paginated<User>> {
    this.requireAdmin();
    const search = (query.search ?? '').trim().toLowerCase();
    const matched = this.db.users.filter(
      (u) =>
        search === '' ||
        u.displayName.toLowerCase().includes(search) ||
        u.email.toLowerCase().includes(search),
    );
    const offset = query.offset ?? 0;
    const limit = query.limit ?? 25;
    return this.delay({
      items: matched.slice(offset, offset + limit),
      total: matched.length,
      offset,
      limit,
    });
  }

  async updateUser(request: UpdateUserRequest): Promise<User> {
    const admin = this.requireAdmin();
    const index = this.db.users.findIndex((u) => u.id === request.userId);
    const existing = this.db.users[index];
    if (existing === undefined) {
      throw notFound('That user');
    }
    if (existing.id === admin.id && request.isAdmin === false) {
      throw conflict('You cannot remove your own organiser rights.');
    }
    const user: User = {
      ...existing,
      ...(request.isAdmin === undefined ? {} : { isAdmin: request.isAdmin }),
      ...(request.isActive === undefined ? {} : { isActive: request.isActive }),
    };
    this.db.users[index] = user;
    return this.delay(user);
  }

  async triggerPasswordReset(request: PasswordResetRequest): Promise<void> {
    this.requireAdmin();
    return this.requestPasswordReset(request);
  }

  async createTournament(request: CreateTournamentRequest): Promise<TournamentDetail> {
    this.requireAdmin();
    const tournament = {
      ...request,
      id: this.generateId('tournament'),
      joinCode: request.visibility === 'PRIVATE' ? this.generateId('code').toUpperCase() : null,
      status: 'DRAFT' as const,
      createdAt: new Date().toISOString(),
    };
    this.db.tournaments.push(tournament);
    return this.delay({ tournament, draws: [], participantCount: 0, participationId: null });
  }

  async updateTournament(request: UpdateTournamentRequest): Promise<TournamentDetail> {
    this.requireAdmin();
    const index = this.db.tournaments.findIndex((t) => t.id === request.tournamentId);
    const existing = this.db.tournaments[index];
    if (existing === undefined) {
      throw notFound('That game');
    }
    const { tournamentId: _ignored, ...changes } = request;
    const tournament = { ...existing, ...changes };
    this.db.tournaments[index] = tournament;
    return this.delay({
      tournament,
      draws: this.db.draws.filter((d) => d.tournamentId === tournament.id),
      participantCount: this.db.participations.filter((p) => p.tournamentId === tournament.id).length,
      participationId: null,
    });
  }

  async createDraw(request: CreateDrawRequest): Promise<Draw> {
    this.requireAdmin();
    this.tournamentOrThrow(request.tournamentId);
    if (this.db.draws.filter((d) => d.tournamentId === request.tournamentId).length >= 2) {
      throw conflict('A game has at most two draws.');
    }
    const draw: Draw = { ...request, id: this.generateId('draw') };
    this.db.draws.push(draw);
    for (let index = 1; index <= 8; index += 1) {
      this.db.sections.push({ id: `${draw.id}-section-${String(index)}`, drawId: draw.id, index });
    }
    return this.delay(draw);
  }

  async putDrawEntries(request: PutDrawEntriesRequest): Promise<readonly DrawSectionWithEntries[]> {
    this.requireAdmin();
    const sections = this.db.sections.filter((s) => s.drawId === request.drawId);
    if (sections.length === 0) {
      throw notFound('That draw');
    }
    const sectionByIndex = new Map(sections.map((s) => [s.index, s]));
    this.db.entries = this.db.entries.filter((e) => e.drawId !== request.drawId);
    for (const input of request.entries) {
      const section = sectionByIndex.get(input.sectionIndex);
      if (section === undefined) {
        throw validationFailed(`Section ${String(input.sectionIndex)} does not exist in this draw.`);
      }
      this.db.entries.push({
        id: `${request.drawId}-e-${input.playerId}`,
        drawId: request.drawId,
        sectionId: section.id,
        playerId: input.playerId,
        seed: input.seed,
      });
    }
    return this.delay(this.sectionsWithEntries(request.drawId));
  }

  async createBetGroup(request: CreateBetGroupRequest): Promise<BetGroup> {
    this.requireAdmin();
    this.tournamentOrThrow(request.tournamentId);
    const group: BetGroup = { ...request, id: this.generateId('bg'), status: 'DRAFT' };
    this.db.betGroups.push(group);
    return this.delay(group);
  }

  async updateBetGroup(request: UpdateBetGroupRequest): Promise<BetGroup> {
    this.requireAdmin();
    const index = this.db.betGroups.findIndex((g) => g.id === request.betGroupId);
    const existing = this.db.betGroups[index];
    if (existing === undefined) {
      throw notFound('That bet group');
    }
    const { betGroupId: _ignored, ...changes } = request;
    const group = { ...existing, ...changes };
    this.db.betGroups[index] = group;
    return this.delay(group);
  }

  async createQuestion(request: CreateQuestionRequest): Promise<Question> {
    this.requireAdmin();
    this.groupOrThrow(request.betGroupId);
    const question: Question = { ...request, id: this.generateId('q'), deadlineOverride: null };
    this.db.questions.push(question);
    return this.delay(question);
  }

  async updateQuestion(request: UpdateQuestionRequest): Promise<Question> {
    this.requireAdmin();
    const index = this.db.questions.findIndex((q) => q.id === request.questionId);
    const existing = this.db.questions[index];
    if (existing === undefined) {
      throw notFound('That question');
    }
    const { questionId: _ignored, ...changes } = request;
    const question = { ...existing, ...changes };
    this.db.questions[index] = question;
    return this.delay(question);
  }

  async putDrawOutcomes(request: PutDrawOutcomesRequest): Promise<readonly DrawSectionWithEntries[]> {
    this.requireAdmin();
    const draw = this.db.draws.find((d) => d.id === request.drawId);
    if (draw === undefined) {
      throw notFound('That draw');
    }
    const entrants = new Set(this.db.entries.filter((e) => e.drawId === draw.id).map((e) => e.playerId));
    for (const entry of request.entries) {
      if (!entrants.has(entry.playerId)) {
        throw validationFailed('That player is not in this draw.');
      }
    }
    this.db.outcomes = this.db.outcomes.filter((o) => o.drawId !== draw.id);
    this.db.outcomes.push(...request.entries.map((e) => ({ ...e, drawId: draw.id })));
    return this.delay(this.sectionsWithEntries(draw.id));
  }

  async putQuestionOutcome(request: PutQuestionOutcomeRequest): Promise<void> {
    this.requireAdmin();
    const question = this.questionOrThrow(request.questionId);
    const expected = expectedPayloadKind(question);
    if (request.correctAnswer.kind !== expected) {
      throw validationFailed(`This question settles with a ${expected} answer.`);
    }
    this.db.questionOutcomes = this.db.questionOutcomes.filter((o) => o.questionId !== question.id);
    this.db.questionOutcomes.push({
      questionId: question.id,
      correctAnswer: request.correctAnswer,
      settledAt: new Date().toISOString(),
      note: request.note,
    });
    return this.delay(undefined);
  }

  /**
   * In the mock this clears the derived score entries and reports what it did.
   * The real engine lives in the backend (AGENTS.md rules 2 and 5), so nothing
   * here recomputes points — it demonstrates that scores are rebuildable.
   */
  async recalculateScores(tournamentId: TournamentId): Promise<RecalculateResult> {
    this.requireAdmin();
    this.tournamentOrThrow(tournamentId);
    const questionIds = new Set(this.questionIdsFor(tournamentId));
    const written = this.db.scores.filter((s) => questionIds.has(s.questionId)).length;
    return this.delay({
      tournamentId,
      scoreEntriesWritten: written,
      calculatedAt: new Date().toISOString(),
    });
  }

  async listPlayers(query: ListPlayersQuery): Promise<readonly Player[]> {
    this.requireAdmin();
    const search = (query.search ?? '').trim().toLowerCase();
    return this.delay(
      this.db.players
        .filter((p) => query.tour === undefined || p.tour === query.tour)
        .filter((p) => search === '' || p.fullName.toLowerCase().includes(search))
        .slice(0, 50),
    );
  }

  async createPlayer(request: CreatePlayerRequest): Promise<Player> {
    this.requireAdmin();
    const player: Player = { ...request, id: this.generateId('player') };
    this.db.players.push(player);
    return this.delay(player);
  }
}
