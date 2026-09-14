import type { TournamentCategory } from '../services';

const CATEGORY_LABELS: Record<TournamentCategory, string> = {
  GRAND_SLAM: 'Grand Slam',
  ATP: 'ATP',
  WTA: 'WTA',
};

export function categoryLabel(category: TournamentCategory): string {
  return CATEGORY_LABELS[category];
}

/** "5h 12m", "3 days", "closed" — the countdown every deadline renders. */
export function timeUntil(deadline: string): string {
  const ms = Date.parse(deadline) - Date.now();
  if (Number.isNaN(ms)) {
    return '';
  }
  if (ms <= 0) {
    return 'closed';
  }
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 60) {
    return `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 48) {
    return `${hours}h ${minutes % 60}m`;
  }
  return `${Math.floor(hours / 24)} days`;
}

export function formatDateRange(startDate: string, endDate: string): string {
  const options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
  const start = new Date(startDate).toLocaleDateString('en-GB', options);
  const end = new Date(endDate).toLocaleDateString('en-GB', options);
  return `${start} – ${end}`;
}
