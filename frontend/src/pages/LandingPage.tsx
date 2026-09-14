import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useNextGame } from '../hooks/queries';
import { Logo, SurfaceBadge } from '../components/ui';
import { categoryLabel, formatDateRange, timeUntil } from '../components/format';

const STEPS: readonly { title: string; body: string }[] = [
  {
    title: 'Before a ball is struck',
    body: 'One quarter-finalist from each of the eight sections, then narrow to four, two and a champion. Nominate a top-ten seed to flop and an unseeded player to run.',
  },
  {
    title: 'Round by round',
    body: 'A new set of bets opens with each round. Call the featured match, its set score, and whatever else the organiser has cooked up.',
  },
  {
    title: 'The deadline locks it',
    body: "When a round closes, everyone's picks become visible at once. No late edits, no excuses.",
  },
  {
    title: 'Points, then bragging rights',
    body: 'The organiser enters each result once. Every score recalculates with a line explaining exactly where your points came from.',
  },
];

/**
 * Spec 4.1. Static copy lives here as a typed constant and changes by commit
 * (decision D13). The teaser is the one live block, and the page must render
 * without it: a failed query degrades to a neutral state, never an error.
 */
export function LandingPage(): ReactNode {
  const teaser = useNextGame();

  return (
    <div className="phone-shell">
      <header className="relative overflow-hidden bg-court px-6 pt-6 pb-16">
        <svg
          viewBox="0 0 240 360"
          className="pointer-events-none absolute -right-14 top-24 w-[300px] opacity-[0.09]"
          fill="none"
          stroke="#faf6ef"
          strokeWidth="2"
          aria-hidden
        >
          <rect x="20" y="10" width="200" height="340" />
          <line x1="20" y1="180" x2="220" y2="180" />
          <rect x="20" y="78" width="200" height="204" />
          <line x1="120" y1="78" x2="120" y2="282" />
        </svg>

        <div className="relative">
          <Logo tone="bone" />
          <p className="mt-11 text-[11px] font-semibold tracking-[0.12em] uppercase text-court-pale">
            For people who watch too much tennis
          </p>
          <h1 className="mt-3 font-display text-5xl leading-[1.02] text-paper text-pretty">
            Call the draw.
            <br />
            Settle it properly.
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-court-pale text-pretty">
            Pick a quarter-finalist from each of the eight sections before a ball is struck. Then bet
            round by round as the draw falls apart. One leaderboard, no money, no spreadsheet.
          </p>
          <Link
            to="/sign-up"
            className="mt-7 flex h-13 items-center justify-center rounded bg-clay text-base font-semibold text-card"
          >
            Create your account
          </Link>
          <p className="mt-4 text-center text-sm text-court-pale">
            Already playing?{' '}
            <Link to="/sign-in" className="border-b border-court-light text-paper">
              Sign in
            </Link>
          </p>
        </div>
      </header>

      <div className="px-5">
        <section className="-mt-10 rounded border border-line border-t-[3px] border-t-clay bg-card p-5 shadow-[0_8px_24px_rgb(30_27_22/0.08)]">
          {teaser.isPending ? (
            <p className="text-sm text-faint">Looking for the next game…</p>
          ) : teaser.data === null || teaser.data === undefined ? (
            <>
              <p className="text-[11px] font-semibold tracking-[0.1em] uppercase text-faint">
                No game currently open
              </p>
              <p className="mt-2 text-sm text-muted text-pretty">
                Nothing is taking signups right now. Create an account and you will be here when the
                next draw is made.
              </p>
            </>
          ) : (
            <>
              <p className="flex items-center gap-2 text-[11px] font-semibold tracking-[0.1em] uppercase text-clay">
                <span className="h-[7px] w-[7px] rounded-full bg-clay" />
                Next game · open for signup
              </p>
              <h2 className="mt-2 font-display text-3xl leading-tight">{teaser.data.name}</h2>
              <p className="mt-1.5 text-sm text-muted">
                {formatDateRange(teaser.data.startDate, teaser.data.endDate)} ·{' '}
                {categoryLabel(teaser.data.category)} · {teaser.data.location}
              </p>
              <div className="mt-4 flex items-center gap-3 border-t border-line pt-4">
                <div className="grow">
                  <p className="font-mono text-xl font-semibold text-court">
                    {timeUntil(teaser.data.signupDeadline)}
                  </p>
                  <p className="text-xs text-muted">until signup closes</p>
                </div>
                <SurfaceBadge surface={teaser.data.surface} />
              </div>
              <Link
                to="/sign-up"
                className="mt-4 flex h-12 items-center justify-center rounded border-[1.5px] border-court text-[15px] font-semibold text-court"
              >
                Sign up and join
              </Link>
            </>
          )}
        </section>

        <section className="pt-12">
          <h2 className="text-[11px] font-semibold tracking-[0.12em] uppercase text-muted">How it works</h2>
          <ol className="mt-5 flex flex-col gap-6">
            {STEPS.map((step, index) => (
              <li key={step.title} className="flex gap-4">
                <span className="w-8 shrink-0 font-display text-3xl leading-none text-clay">{index + 1}</span>
                <div>
                  <h3 className="font-semibold">{step.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted text-pretty">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <footer className="mt-12 bg-court px-6 py-8 text-court-pale">
        <Logo tone="bone" />
        <p className="mt-3.5 text-[13px] leading-relaxed text-pretty">
          Not a betting service. No money changes hands, no odds are offered, nothing is paid out.
        </p>
      </footer>
    </div>
  );
}
