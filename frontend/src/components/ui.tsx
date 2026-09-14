import type { ReactNode } from 'react';
import { isApiError } from '../services';
import type { Surface } from '../services';

export function Spinner({ label }: { label: string }): ReactNode {
  return (
    <div className="flex items-center gap-3 px-5 py-10 text-sm text-muted" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line-strong border-t-clay" />
      {label}
    </div>
  );
}

/**
 * Renders whatever the API said went wrong. It never invents a message: an
 * RFC 7807 problem carries its own detail, and the backend is the authority
 * on why something was refused.
 */
export function Problem({ error }: { error: unknown }): ReactNode {
  if (error === null || error === undefined) {
    return null;
  }
  const detail = isApiError(error)
    ? error.problem.detail
    : error instanceof Error
      ? error.message
      : 'Something went wrong.';
  const fields = isApiError(error) ? Object.values(error.fieldErrors).flat() : [];

  return (
    <div role="alert" className="rounded border border-clay/40 bg-clay-soft px-4 py-3 text-sm text-clay-dark">
      <p className="font-semibold">{detail}</p>
      {fields.length > 0 && (
        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-clay-dark/80">
          {fields.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }): ReactNode {
  return (
    <div className="rounded border border-dashed border-line-strong px-5 py-8 text-center text-sm text-faint">
      {children}
    </div>
  );
}

const SURFACE_STYLES: Record<Surface, string> = {
  CLAY: 'bg-clay-soft text-clay-dark',
  GRASS: 'bg-court-soft text-court',
  HARD: 'bg-[#e4e6ec] text-[#4a5367]',
  INDOOR_HARD: 'bg-[#e8e4ec] text-[#54476a]',
};

const SURFACE_LABELS: Record<Surface, string> = {
  CLAY: 'Clay',
  GRASS: 'Grass',
  HARD: 'Hard',
  INDOOR_HARD: 'Indoor',
};

export function SurfaceBadge({ surface }: { surface: Surface }): ReactNode {
  return (
    <span className={`rounded px-2 py-1 text-[10px] font-semibold tracking-wider uppercase ${SURFACE_STYLES[surface]}`}>
      {SURFACE_LABELS[surface]}
    </span>
  );
}

export function Logo({ tone = 'clay' }: { tone?: 'clay' | 'bone' }): ReactNode {
  const stroke = tone === 'clay' ? 'var(--color-clay)' : '#d98a5e';
  const text = tone === 'clay' ? 'text-court' : 'text-paper';
  return (
    <span className="flex items-center gap-2">
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke={stroke} strokeWidth="1.6" aria-hidden>
        <circle cx="12" cy="12" r="9.5" />
        <path d="M4.2 6.5c3.6 2.1 5.4 5.3 5.1 10.8" />
        <path d="M19.8 6.5c-3.6 2.1-5.4 5.3-5.1 10.8" />
      </svg>
      <span className={`text-xs font-semibold tracking-[0.14em] uppercase ${text}`}>Deuce</span>
    </span>
  );
}
