/**
 * Deterministic helpers for fixture construction.
 *
 * Fixtures must be the same on every run: a test that passes today has to pass
 * tomorrow, and a screenshot taken in review has to match what the next person
 * sees. Nothing here reads the clock or calls `Math.random`.
 */

/** mulberry32 — small, fast, and stable across engines. */
export function createRandom(seed: number): () => number {
  let state = seed >>> 0;
  return function next(): number {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function pick<T>(random: () => number, items: readonly T[]): T {
  const item = items[Math.floor(random() * items.length)];
  if (item === undefined) {
    throw new Error('pick() called with an empty list');
  }
  return item;
}

/** Fisher-Yates against the supplied generator, leaving the input untouched. */
export function shuffle<T>(random: () => number, items: readonly T[]): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    const a = out[i];
    const b = out[j];
    if (a !== undefined && b !== undefined) {
      out[i] = b;
      out[j] = a;
    }
  }
  return out;
}

/**
 * Fixture clock — read once per process, then frozen.
 *
 * Every timestamp in the fixtures is expressed relative to this instant, so
 * "the quarter-final group closes in five hours" stays true whenever the app
 * is opened. Freezing it is what makes two builds in the same run identical:
 * without it, fixtures built milliseconds apart disagree about `now`, and
 * every game in one database would be anchored to a slightly different moment.
 */
let epoch: number | null = null;

export function fixtureNow(): Date {
  epoch ??= Date.now();
  return new Date(epoch);
}

export function hoursFromNow(hours: number): string {
  return new Date(fixtureNow().getTime() + hours * 3_600_000).toISOString();
}

export function daysFromNow(days: number): string {
  return hoursFromNow(days * 24);
}

export function dateOnly(isoDateTime: string): string {
  const [date] = isoDateTime.split('T');
  if (date === undefined) {
    throw new Error(`not an ISO timestamp: ${isoDateTime}`);
  }
  return date;
}

/** Stable, readable identifiers — `rg-atp-section-3` beats a random uuid. */
export function id(...parts: readonly (string | number)[]): string {
  return parts.join('-');
}
