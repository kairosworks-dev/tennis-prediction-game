import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within, type RenderResult } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ApiProvider } from '../../hooks/ApiProvider';
import { BetsTab } from './BetsTab';
import { createTestApiClient } from '../../services/testing';
import { legalSetScores } from '../../services';
import type { ApiClient, Prediction, PredictionPayload, Question } from '../../services';

/**
 * The Submit button is labelled from the stored prediction, never from the
 * state of a mutation in this mount (issue #38). Every test builds the stored
 * state through `client.putPrediction`; none reads a seed fixture's contents.
 */

interface Game {
  readonly client: ApiClient;
  readonly tournamentId: string;
  readonly integer: Question;
  readonly match: Question & { readonly matchup: readonly [string, string] };
  readonly scores: readonly string[];
  readonly names: ReadonlyMap<string, string>;
}

async function openGame(): Promise<Game> {
  const client = createTestApiClient({ signedIn: true });
  for (const summary of await client.listTournaments()) {
    const tournamentId = summary.tournament.id;
    const group = (await client.listBetGroups(tournamentId)).find((g) => g.status === 'OPEN');
    if (group === undefined) continue;

    const questions = await client.listQuestions(tournamentId, group.id);
    const integer = questions.find((q) => q.answerType === 'INTEGER');
    const match = questions.find((q) => q.answerType === 'MATCH_RESULT' && q.matchup !== null);
    if (integer === undefined || match?.matchup == null) {
      throw new Error('the mock has no open group with an integer and a match-result question');
    }
    const draw = (await client.listDraws(tournamentId)).find((d) => d.id === match.drawId);
    const sections = await client.listDrawEntries(tournamentId, match.drawId ?? '');
    const names = new Map(
      sections.flatMap((s) => s.entries).map((e) => [e.player.id, e.player.fullName] as const),
    );
    return {
      client,
      tournamentId,
      integer,
      match: { ...match, matchup: match.matchup },
      scores: legalSetScores(draw?.bestOf ?? 3),
      names,
    };
  }
  throw new Error('the mock has no game with an open group');
}

function renderTab(game: Game): RenderResult {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ApiProvider client={game.client}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <BetsTab tournamentId={game.tournamentId} />
        </MemoryRouter>
      </QueryClientProvider>
    </ApiProvider>,
  );
}

const integerAnswer = (value: number): PredictionPayload => ({ kind: 'GENERIC_INTEGER', value });

async function store(game: Game, question: Question, payload: PredictionPayload, asDraft: boolean): Promise<Prediction> {
  return game.client.putPrediction({ tournamentId: game.tournamentId, questionId: question.id, payload, asDraft });
}

async function formFor(question: Question): Promise<HTMLElement> {
  return screen.findByRole('group', { name: question.prompt });
}

/** The Submit button, whichever of its two labels it carries. */
function submitButton(form: HTMLElement): HTMLElement {
  return within(form).getByRole('button', { name: /^Submit(ted)?$/ });
}

describe('the Submit button label, by stored state', () => {
  it('reads Submit when nothing is stored', async () => {
    const game = await openGame();
    vi.spyOn(game.client, 'listOwnPredictions').mockResolvedValue([]);
    renderTab(game);

    const form = await formFor(game.integer);
    expect(submitButton(form)).toHaveTextContent(/^Submit$/);
  });

  it('reads Submit when the stored answer is a draft', async () => {
    const game = await openGame();
    await store(game, game.integer, integerAnswer(3), true);
    renderTab(game);

    const form = await formFor(game.integer);
    expect(within(form).getByRole('status')).toHaveTextContent('3');
    expect(submitButton(form)).toHaveTextContent(/^Submit$/);
  });

  it('reads Submitted when the stored answer is submitted and the form shows it', async () => {
    const game = await openGame();
    await store(game, game.integer, integerAnswer(3), false);
    renderTab(game);

    const form = await formFor(game.integer);
    expect(within(form).getByRole('status')).toHaveTextContent('3');
    expect(submitButton(form)).toHaveTextContent(/^Submitted$/);
  });

  it('reads Submit when the stored answer is submitted but the form shows another', async () => {
    const game = await openGame();
    await store(game, game.integer, integerAnswer(3), false);
    renderTab(game);

    const form = await formFor(game.integer);
    await userEvent.click(within(form).getByRole('button', { name: 'one more' }));
    expect(submitButton(form)).toHaveTextContent(/^Submit$/);
  });
});

/** Waits for the server to hold this answer, then for the form to be idle again. */
async function savedAs(game: Game, question: Question, submitted: boolean, form: HTMLElement): Promise<void> {
  await waitFor(async () => {
    const own = await game.client.listOwnPredictions(game.tournamentId);
    const held = own.find((p) => p.questionId === question.id);
    expect(held?.submittedAt === null).toBe(!submitted);
  });
  await waitFor(() => { expect(within(form).getByRole('button', { name: 'Save draft' })).toBeEnabled(); });
}

describe('the Submit button label, over a session', () => {
  it('reads Submit, with the pick still shown, after Save draft succeeds', async () => {
    const game = await openGame();
    await store(game, game.integer, integerAnswer(3), false);
    renderTab(game);
    const form = await formFor(game.integer);

    await userEvent.click(within(form).getByRole('button', { name: 'one more' }));
    await userEvent.click(within(form).getByRole('button', { name: 'Save draft' }));
    await savedAs(game, game.integer, false, form);

    expect(submitButton(form)).toHaveTextContent(/^Submit$/);
    expect(within(form).getByRole('status')).toHaveTextContent('4');
  });

  it('reads Submitted after Submit succeeds', async () => {
    const game = await openGame();
    renderTab(game);
    const form = await formFor(game.integer);

    await userEvent.click(within(form).getByRole('button', { name: 'one more' }));
    await userEvent.click(submitButton(form));

    await waitFor(() => { expect(submitButton(form)).toHaveTextContent(/^Submitted$/); });
  });

  it('reads Submitted after a remount on the same client, with the pick shown', async () => {
    const game = await openGame();
    const first = renderTab(game);
    const before = await formFor(game.integer);
    await userEvent.click(within(before).getByRole('button', { name: 'one more' }));
    await userEvent.click(submitButton(before));
    await waitFor(() => { expect(submitButton(before)).toHaveTextContent(/^Submitted$/); });
    const shown = within(before).getByRole('status').textContent;
    first.unmount();

    renderTab(game);
    const form = await formFor(game.integer);
    expect(within(form).getByRole('status')).toHaveTextContent(shown);
    expect(submitButton(form)).toHaveTextContent(/^Submitted$/);
  });

  it('reads Submitted after the group is collapsed and opened again', async () => {
    const game = await openGame();
    await store(game, game.integer, integerAnswer(3), false);
    renderTab(game);
    await formFor(game.integer);

    const header = screen.getByRole('button', { expanded: true });
    await userEvent.click(header);
    expect(screen.queryByRole('group', { name: game.integer.prompt })).not.toBeInTheDocument();
    await userEvent.click(header);

    const form = await formFor(game.integer);
    expect(submitButton(form)).toHaveTextContent(/^Submitted$/);
  });

  it('follows the form against the stored answer: edit, then revert', async () => {
    const game = await openGame();
    await store(game, game.integer, integerAnswer(3), false);
    renderTab(game);
    const form = await formFor(game.integer);

    await userEvent.click(within(form).getByRole('button', { name: 'one more' }));
    expect(submitButton(form)).toHaveTextContent(/^Submit$/);
    await userEvent.click(within(form).getByRole('button', { name: 'one fewer' }));
    expect(submitButton(form)).toHaveTextContent(/^Submitted$/);
  });

  it('follows a different set score and a different winner, then reverts', async () => {
    const game = await openGame();
    const [first, second] = game.scores;
    const [home, away] = game.match.matchup;
    if (first === undefined || second === undefined) throw new Error('a draw offers at least two set scores');
    await store(game, game.match, { kind: 'GENERIC_MATCH_RESULT', winnerId: home, setScore: first as never }, false);
    renderTab(game);
    const form = await formFor(game.match);
    expect(submitButton(form)).toHaveTextContent(/^Submitted$/);

    await userEvent.click(within(form).getByRole('button', { name: second }));
    expect(submitButton(form)).toHaveTextContent(/^Submit$/);
    await userEvent.click(within(form).getByRole('button', { name: first }));
    expect(submitButton(form)).toHaveTextContent(/^Submitted$/);

    await userEvent.click(within(form).getByRole('button', { name: new RegExp(game.names.get(away) ?? away) }));
    expect(submitButton(form)).toHaveTextContent(/^Submit$/);
    await userEvent.click(within(form).getByRole('button', { name: new RegExp(game.names.get(home) ?? home) }));
    expect(submitButton(form)).toHaveTextContent(/^Submitted$/);
  });

  it('reads Submit after Save draft over a submitted answer, same or changed', async () => {
    const game = await openGame();
    await store(game, game.integer, integerAnswer(3), false);
    renderTab(game);
    const form = await formFor(game.integer);
    expect(submitButton(form)).toHaveTextContent(/^Submitted$/);

    await userEvent.click(within(form).getByRole('button', { name: 'Save draft' }));
    await savedAs(game, game.integer, false, form);

    expect(submitButton(form)).toHaveTextContent(/^Submit$/);
  });

  it('reads Submitted after Submit with a changed answer', async () => {
    const game = await openGame();
    await store(game, game.integer, integerAnswer(3), false);
    renderTab(game);
    const form = await formFor(game.integer);

    await userEvent.click(within(form).getByRole('button', { name: 'one more' }));
    await userEvent.click(submitButton(form));

    await waitFor(() => { expect(submitButton(form)).toHaveTextContent(/^Submitted$/); });
    const own = await game.client.listOwnPredictions(game.tournamentId);
    expect(own.find((p) => p.questionId === game.integer.id)?.payload).toEqual(integerAnswer(4));
  });

  it('does not change the label when a save fails, and does not disable Submit when Submitted', async () => {
    const game = await openGame();
    await store(game, game.integer, integerAnswer(3), false);
    vi.spyOn(game.client, 'putPrediction').mockRejectedValue(new Error('the server said no'));
    renderTab(game);
    const form = await formFor(game.integer);
    expect(submitButton(form)).toBeEnabled();

    await userEvent.click(within(form).getByRole('button', { name: 'Save draft' }));

    expect(await within(form).findByRole('alert')).toHaveTextContent('the server said no');
    expect(submitButton(form)).toHaveTextContent(/^Submitted$/);
  });
});

describe('a group waits for the own predictions', () => {
  it('shows a spinner, then the form with the stored answer', async () => {
    const game = await openGame();
    await store(game, game.integer, integerAnswer(3), false);
    const loaded = await game.client.listOwnPredictions(game.tournamentId);
    let release: (value: readonly Prediction[]) => void = () => undefined;
    vi.spyOn(game.client, 'listOwnPredictions').mockReturnValue(
      new Promise((resolve) => { release = resolve; }),
    );
    renderTab(game);

    expect(await screen.findByText('Loading your answers…')).toBeInTheDocument();
    expect(screen.queryByRole('group', { name: game.integer.prompt })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Submit(ted)?$/ })).not.toBeInTheDocument();

    release(loaded);
    const form = await formFor(game.integer);
    expect(within(form).getByRole('status')).toHaveTextContent('3');
    expect(submitButton(form)).toHaveTextContent(/^Submitted$/);
  });

  it('shows a problem, and no form, when they fail to load', async () => {
    const game = await openGame();
    vi.spyOn(game.client, 'listOwnPredictions').mockRejectedValue(new Error('could not load'));
    renderTab(game);

    expect(await screen.findByRole('alert')).toHaveTextContent('could not load');
    expect(screen.queryByRole('group', { name: game.integer.prompt })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Submit(ted)?$/ })).not.toBeInTheDocument();
  });
});
