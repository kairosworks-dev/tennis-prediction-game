import { useState, type ReactNode } from 'react';
import type { DrawSectionWithEntries, SectionPick } from '../../services';

type EntryRow = DrawSectionWithEntries['entries'][number];

/**
 * Quarter-finalists: one player from each of the eight sections.
 *
 * One section open at a time, because sixteen entrants across eight sections
 * is a hundred and twenty-eight rows on a phone otherwise. Choosing advances
 * to the next unanswered section; the header stays tappable so a finished set
 * can still be reopened.
 */
export function SectionPicker({
  sections,
  value,
  onChange,
}: {
  sections: readonly DrawSectionWithEntries[];
  value: readonly SectionPick[];
  onChange: (picks: readonly SectionPick[]) => void;
}): ReactNode {
  const [open, setOpen] = useState<number | null>(1);

  if (sections.length === 0) {
    return <p className="text-[13px] text-faint">The draw has not been published yet.</p>;
  }

  const pickFor = (index: number): SectionPick | undefined =>
    value.find((pick) => pick.sectionIndex === index);

  const choose = (sectionIndex: number, playerId: string): void => {
    const next = [...value.filter((pick) => pick.sectionIndex !== sectionIndex), { sectionIndex, playerId }];
    onChange(next.sort((a, b) => a.sectionIndex - b.sectionIndex));
    const nextEmpty = sections
      .map((section) => section.section.index)
      .find((index) => index !== sectionIndex && !next.some((pick) => pick.sectionIndex === index));
    setOpen(nextEmpty ?? null);
  };

  return (
    <>
      <p className="mb-2.5 text-[13px] text-muted">
        <span className={`font-mono font-semibold ${value.length === 8 ? 'text-court' : 'text-clay'}`}>
          {value.length} of 8
        </span>{' '}
        chosen.
      </p>
      <ul className="flex flex-col gap-2">
        {sections.map(({ section, entries }) => {
          const pick = pickFor(section.index);
          const picked = entries.find((row) => row.player.id === pick?.playerId);
          const isOpen = open === section.index;

          return (
            <li
              key={section.id}
              className={`overflow-hidden rounded border bg-card ${
                picked !== undefined ? 'border-line-strong' : isOpen ? 'border-clay' : 'border-line'
              }`}
            >
              <button
                type="button"
                onClick={() => { setOpen(isOpen ? null : section.index); }}
                aria-expanded={isOpen}
                className={`flex w-full items-center gap-3 px-3.5 py-3.5 text-left ${isOpen ? 'bg-clay-soft' : ''}`}
              >
                <span
                  className={`flex h-6.5 w-6.5 shrink-0 items-center justify-center rounded-full font-mono text-xs font-semibold ${
                    picked !== undefined ? 'bg-court text-paper' : 'bg-sunk text-faint'
                  }`}
                >
                  {section.index}
                </span>
                <span
                  className={`grow text-[15px] ${picked !== undefined ? 'font-semibold' : 'text-faint'}`}
                >
                  {picked?.player.fullName ?? 'Choose a player'}
                </span>
                <svg viewBox="0 0 24 24" className="h-4.5 w-4.5 shrink-0" fill="none" stroke="#9a8b76" strokeWidth="1.9">
                  <path d={isOpen ? 'M6 14.5L12 8.5l6 6' : 'M6 9.5l6 6 6-6'} />
                </svg>
              </button>

              {isOpen && (
                <ul className="flex flex-col gap-1.5 border-t border-line/60 px-2.5 pt-1 pb-3">
                  {entries.slice(0, 8).map((row) => (
                    <li key={row.entry.id}>
                      <PlayerRow row={row} selected={row.player.id === pick?.playerId} onSelect={() => { choose(section.index, row.player.id); }} />
                    </li>
                  ))}
                  {entries.length > 8 && (
                    <li className="px-3 pt-2 text-xs text-faint">
                      Showing 8 of {entries.length} entrants in this section
                    </li>
                  )}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}

function PlayerRow({
  row,
  selected,
  onSelect,
}: {
  row: EntryRow;
  selected: boolean;
  onSelect: () => void;
}): ReactNode {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`flex w-full items-center gap-2.5 rounded border px-3 py-3 text-left ${
        selected ? 'border-court bg-court text-paper' : 'border-line bg-card text-ink-soft'
      }`}
    >
      <span className={`w-8 shrink-0 font-mono text-[11px] font-semibold ${selected ? 'text-court-pale' : 'text-faint'}`}>
        {row.entry.seed === null ? '—' : `[${row.entry.seed}]`}
      </span>
      <span className="grow text-sm font-medium">{row.player.fullName}</span>
      <span className={`text-[11px] ${selected ? 'text-court-pale' : 'text-faint'}`}>{row.player.countryCode}</span>
    </button>
  );
}

/**
 * A row of tappable players drawn from a pool — the participant's own earlier
 * picks for the cascade, or the eligible entrants for underperformer and
 * breakout. Reaching `max` dims the rest rather than hiding them.
 */
export function PlayerChips({
  pool,
  entries,
  selected,
  max,
  emptyHint,
  showSeeds = false,
  onChange,
}: {
  pool: readonly string[];
  entries: readonly EntryRow[];
  selected: readonly string[];
  max: number;
  emptyHint: string;
  showSeeds?: boolean;
  onChange: (playerIds: readonly string[]) => void;
}): ReactNode {
  if (pool.length === 0) {
    return <p className="text-[13px] text-faint">{emptyHint}</p>;
  }

  const rowFor = (playerId: string): EntryRow | undefined =>
    entries.find((entry) => entry.player.id === playerId);

  const toggle = (playerId: string): void => {
    if (selected.includes(playerId)) {
      onChange(selected.filter((id) => id !== playerId));
      return;
    }
    // A single-answer question replaces rather than refuses.
    onChange(max === 1 ? [playerId] : selected.length < max ? [...selected, playerId] : selected);
  };

  return (
    <>
      {max > 1 && (
        <p className="mb-2.5 text-[13px] text-muted">
          <span className="font-mono font-semibold">
            {selected.length} of {max}
          </span>{' '}
          chosen.
        </p>
      )}
      <ul className="flex flex-wrap gap-2">
        {pool.map((playerId) => {
          const row = rowFor(playerId);
          const on = selected.includes(playerId);
          const dim = !on && max > 1 && selected.length >= max;
          return (
            <li key={playerId}>
              <button
                type="button"
                onClick={() => { toggle(playerId); }}
                aria-pressed={on}
                className={`flex items-center gap-1.5 rounded-full border px-3.5 py-3 text-sm ${
                  on
                    ? 'border-court bg-court font-semibold text-paper'
                    : dim
                      ? 'border-line bg-sunk text-ghost'
                      : 'border-line-strong bg-card font-medium text-ink-soft'
                }`}
              >
                {showSeeds && row !== undefined && row.entry.seed !== null && (
                  <span className={`font-mono text-[11px] font-semibold ${on ? 'text-court-pale' : 'text-faint'}`}>
                    [{row.entry.seed}]
                  </span>
                )}
                {row?.player.fullName ?? playerId}
              </button>
            </li>
          );
        })}
      </ul>
    </>
  );
}
