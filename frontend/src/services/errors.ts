/**
 * RFC 7807 problem details (spec 7.5, AGENTS.md backend conventions).
 *
 * The backend is the authority on validation. The frontend mirrors rules for
 * user experience, but a rejection always arrives in this shape and the UI
 * renders what it is told rather than what it guessed.
 */
export interface ProblemDetail {
  /** A URI reference identifying the problem type. */
  readonly type: string;
  readonly title: string;
  readonly status: number;
  readonly detail: string;
  /** Field-level messages, keyed by a path into the request body. */
  readonly errors?: Readonly<Record<string, readonly string[]>>;
}

export class ApiError extends Error {
  readonly problem: ProblemDetail;

  constructor(problem: ProblemDetail) {
    super(problem.detail);
    this.name = 'ApiError';
    this.problem = problem;
  }

  get status(): number {
    return this.problem.status;
  }

  /** Field-level messages for a form, or an empty object. */
  get fieldErrors(): Readonly<Record<string, readonly string[]>> {
    return this.problem.errors ?? {};
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

const PROBLEM_BASE = 'https://tennis-prediction-game.invalid/problems';

export function problem(
  slug: string,
  status: number,
  title: string,
  detail: string,
  errors?: Readonly<Record<string, readonly string[]>>,
): ApiError {
  return new ApiError(
    errors === undefined
      ? { type: `${PROBLEM_BASE}/${slug}`, title, status, detail }
      : { type: `${PROBLEM_BASE}/${slug}`, title, status, detail, errors },
  );
}

export const notFound = (what: string): ApiError =>
  problem('not-found', 404, 'Not found', `${what} does not exist.`);

export const unauthorized = (): ApiError =>
  problem('unauthorized', 401, 'Not signed in', 'You must be signed in to do that.');

export const forbidden = (detail: string): ApiError =>
  problem('forbidden', 403, 'Not allowed', detail);

export const conflict = (detail: string): ApiError =>
  problem('conflict', 409, 'Conflict', detail);

export const validationFailed = (
  detail: string,
  errors?: Readonly<Record<string, readonly string[]>>,
): ApiError => problem('validation-failed', 422, 'Validation failed', detail, errors);
