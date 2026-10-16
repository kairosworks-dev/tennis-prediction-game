import type { PredictionPayload } from '../../services';

/**
 * A key-order-independent form of an answer, for comparison only.
 *
 * The pickers append in the order the participant taps, the server returns
 * what it stored; the same set of players in a different order is the same
 * answer. Picks are ordered by section, player lists alphabetically.
 */
function canonical(payload: PredictionPayload): unknown {
  switch (payload.kind) {
    case 'QF_PICKS':
      return {
        kind: payload.kind,
        picks: payload.picks
          .map((pick) => [pick.sectionIndex, pick.playerId] as const)
          .sort((a, b) => a[0] - b[0] || a[1].localeCompare(b[1])),
      };
    case 'SF_PICKS':
    case 'FINALIST_PICKS':
      return { kind: payload.kind, playerIds: [...payload.playerIds].sort() };
    default:
      return payload;
  }
}

/** Sorts object keys at every depth, so that key order never matters. */
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
 * Whether the form shows the stored answer. Display only (AGENTS.md rule 2):
 * it decides a button label, never whether anything is allowed.
 */
export function samePayload(a: PredictionPayload | null, b: PredictionPayload | null): boolean {
  if (a === null || b === null) {
    return a === b;
  }
  return stable(canonical(a)) === stable(canonical(b));
}
