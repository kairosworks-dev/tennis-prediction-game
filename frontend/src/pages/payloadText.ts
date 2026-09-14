import type { PredictionPayload } from '../services';

/**
 * Turns a prediction payload into a sentence fragment.
 *
 * Presentation only — it decides nothing and scores nothing. The reason string
 * beside each score comes from the backend and is the authoritative account of
 * why points were awarded.
 */
export function describePayload(
  payload: PredictionPayload | null,
  nameOf: (playerId: string) => string = (id) => id,
): string {
  if (payload === null) {
    return 'nothing yet';
  }
  switch (payload.kind) {
    case 'QF_PICKS':
      return payload.picks.map((pick) => nameOf(pick.playerId)).join(', ');
    case 'SF_PICKS':
    case 'FINALIST_PICKS':
      return payload.playerIds.map(nameOf).join(', ');
    case 'CHAMPION':
    case 'UNDERPERFORMER':
    case 'BREAKOUT':
    case 'GENERIC_PLAYER':
      return nameOf(payload.playerId);
    case 'GENERIC_MATCH_RESULT':
      return `${nameOf(payload.winnerId)} ${payload.setScore}`;
    case 'GENERIC_INTEGER':
      return String(payload.value);
    case 'GENERIC_CHOICE':
      return payload.optionId;
  }
}
