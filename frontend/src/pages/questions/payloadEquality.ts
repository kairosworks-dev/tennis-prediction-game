import type { PredictionPayload } from '../../services';

/**
 * Structural form of a value with object keys sorted at every depth, so that
 * key order never matters. Array order does: whether the order of a list of
 * picks matters is a domain rule, and the frontend holds none (AGENTS.md rule 2).
 */
function stable(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stable).join(',')}]`;
  }
  if (value !== null && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stable(record[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

/**
 * Whether the form shows exactly the stored answer. Display only: it decides a
 * button label, never whether anything is allowed. Plain structural equality;
 * the same players in a different order are a different answer here.
 */
export function samePayload(a: PredictionPayload | null, b: PredictionPayload | null): boolean {
  if (a === null || b === null) {
    return a === b;
  }
  return stable(a) === stable(b);
}
