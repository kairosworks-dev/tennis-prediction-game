import type { Player, Tour } from '../../types';
import { createRandom, id } from './seed';

/**
 * The global player registry.
 *
 * The named players below are real professionals and carry the seedings the
 * fixtures use. A Grand Slam draw holds 128 entrants per tour, so the rest of
 * each field is filled with SYNTHETIC entrants generated deterministically —
 * they exist to make a 128-entry draw render honestly, not to represent
 * anybody. Replace the whole module when real draw data arrives.
 */

interface NamedPlayer {
  readonly fullName: string;
  readonly countryCode: string;
}

const ATP_NAMED: readonly NamedPlayer[] = [
  { fullName: 'Carlos Alcaraz', countryCode: 'ESP' },
  { fullName: 'Jannik Sinner', countryCode: 'ITA' },
  { fullName: 'Alexander Zverev', countryCode: 'GER' },
  { fullName: 'Holger Rune', countryCode: 'DEN' },
  { fullName: 'Taylor Fritz', countryCode: 'USA' },
  { fullName: 'Novak Djokovic', countryCode: 'SRB' },
  { fullName: 'Casper Ruud', countryCode: 'NOR' },
  { fullName: 'Alex de Miñaur', countryCode: 'AUS' },
  { fullName: 'Lorenzo Musetti', countryCode: 'ITA' },
  { fullName: 'Andrey Rublev', countryCode: 'RUS' },
  { fullName: 'Ben Shelton', countryCode: 'USA' },
  { fullName: 'Stefanos Tsitsipas', countryCode: 'GRE' },
  { fullName: 'Jack Draper', countryCode: 'GBR' },
  { fullName: 'Frances Tiafoe', countryCode: 'USA' },
  { fullName: 'Ugo Humbert', countryCode: 'FRA' },
  { fullName: 'Tomáš Macháč', countryCode: 'CZE' },
  { fullName: 'Sebastian Korda', countryCode: 'USA' },
  { fullName: 'Francisco Cerúndolo', countryCode: 'ARG' },
  { fullName: 'Luciano Darderi', countryCode: 'ITA' },
  { fullName: 'Alex Michelsen', countryCode: 'USA' },
  { fullName: 'Jakub Menšík', countryCode: 'CZE' },
  { fullName: 'Arthur Fils', countryCode: 'FRA' },
  { fullName: 'Flavio Cobolli', countryCode: 'ITA' },
  { fullName: 'Matteo Berrettini', countryCode: 'ITA' },
  { fullName: 'Grigor Dimitrov', countryCode: 'BUL' },
  { fullName: 'Jiří Lehecká', countryCode: 'CZE' },
  { fullName: 'Alexander Bublik', countryCode: 'KAZ' },
  { fullName: 'Alexei Popyrin', countryCode: 'AUS' },
  { fullName: 'Tallon Griekspoor', countryCode: 'NED' },
  { fullName: 'Sebastián Báez', countryCode: 'ARG' },
  { fullName: 'Brandon Nakashima', countryCode: 'USA' },
  { fullName: 'Jan-Lennard Struff', countryCode: 'GER' },
];

const WTA_NAMED: readonly NamedPlayer[] = [
  { fullName: 'Aryna Sabalenka', countryCode: 'BLR' },
  { fullName: 'Iga Świątek', countryCode: 'POL' },
  { fullName: 'Coco Gauff', countryCode: 'USA' },
  { fullName: 'Jasmine Paolini', countryCode: 'ITA' },
  { fullName: 'Elena Rybakina', countryCode: 'KAZ' },
  { fullName: 'Mirra Andreeva', countryCode: 'RUS' },
  { fullName: 'Jessica Pegula', countryCode: 'USA' },
  { fullName: 'Qinwen Zheng', countryCode: 'CHN' },
  { fullName: 'Emma Navarro', countryCode: 'USA' },
  { fullName: 'Daria Kasatkina', countryCode: 'AUS' },
  { fullName: 'Paula Badosa', countryCode: 'ESP' },
  { fullName: 'Diana Shnaider', countryCode: 'RUS' },
  { fullName: 'Barbora Krejčíková', countryCode: 'CZE' },
  { fullName: 'Karolína Muchová', countryCode: 'CZE' },
  { fullName: 'Beatriz Haddad Maia', countryCode: 'BRA' },
  { fullName: 'Donna Vekić', countryCode: 'CRO' },
  { fullName: 'Marta Kostyuk', countryCode: 'UKR' },
  { fullName: 'Victoria Azarenka', countryCode: 'BLR' },
  { fullName: 'Ons Jabeur', countryCode: 'TUN' },
  { fullName: 'Elina Svitolina', countryCode: 'UKR' },
  { fullName: 'Leylah Fernandez', countryCode: 'CAN' },
  { fullName: 'Magda Linette', countryCode: 'POL' },
  { fullName: 'Clara Tauson', countryCode: 'DEN' },
  { fullName: 'Anna Kalinskaya', countryCode: 'RUS' },
  { fullName: 'Linda Nosková', countryCode: 'CZE' },
  { fullName: 'Katie Boulter', countryCode: 'GBR' },
  { fullName: 'Sofia Kenin', countryCode: 'USA' },
  { fullName: 'Caroline Garcia', countryCode: 'FRA' },
  { fullName: 'Veronika Kudermetova', countryCode: 'RUS' },
  { fullName: 'Yulia Putintseva', countryCode: 'KAZ' },
  { fullName: 'Camila Osorio', countryCode: 'COL' },
  { fullName: 'Lucia Bronzetti', countryCode: 'ITA' },
];

/* Components for the synthetic remainder of each field. */
const FILLER_FIRST = [
  'Andres', 'Bjorn', 'Cedric', 'Dario', 'Emil', 'Fabio', 'Gustav', 'Hugo',
  'Ivan', 'Janek', 'Kasper', 'Luka', 'Milos', 'Nuno', 'Otto', 'Pavel',
] as const;
const FILLER_FIRST_WTA = [
  'Adela', 'Brigita', 'Carla', 'Dana', 'Elsa', 'Frida', 'Greta', 'Hana',
  'Ilona', 'Jana', 'Katia', 'Lena', 'Mira', 'Nela', 'Olga', 'Petra',
] as const;
const FILLER_LAST = [
  'Almeida', 'Brandt', 'Corradi', 'Dvorak', 'Engberg', 'Ferrer', 'Gustafsson',
  'Holm', 'Ivanov', 'Jansen', 'Kowalski', 'Lindqvist', 'Moravec', 'Novotny',
  'Olsen', 'Pereira', 'Quintana', 'Rossi', 'Sandberg', 'Toth', 'Urban',
  'Vogel', 'Weiss', 'Zima',
] as const;
const FILLER_COUNTRIES = [
  'ARG', 'AUT', 'BEL', 'BRA', 'CHI', 'COL', 'CRO', 'DEN', 'FIN', 'GEO',
  'HUN', 'IND', 'JPN', 'KOR', 'NOR', 'POR', 'ROU', 'SVK', 'SWE', 'SUI',
] as const;

const DRAW_SIZE = 128;

function buildTour(tour: Tour, named: readonly NamedPlayer[], seed: number): Player[] {
  const random = createRandom(seed);
  const firstNames = tour === 'ATP' ? FILLER_FIRST : FILLER_FIRST_WTA;
  const players: Player[] = named.map((p, index) => ({
    id: id(tour.toLowerCase(), 'p', index + 1),
    fullName: p.fullName,
    countryCode: p.countryCode,
    tour,
  }));

  const used = new Set(players.map((p) => p.fullName));
  let index = named.length;
  while (players.length < DRAW_SIZE) {
    const first = firstNames[Math.floor(random() * firstNames.length)] ?? 'Alex';
    const last = FILLER_LAST[Math.floor(random() * FILLER_LAST.length)] ?? 'Novak';
    const fullName = `${first} ${last}`;
    if (used.has(fullName)) {
      continue;
    }
    used.add(fullName);
    index += 1;
    players.push({
      id: id(tour.toLowerCase(), 'p', index),
      fullName,
      countryCode: FILLER_COUNTRIES[Math.floor(random() * FILLER_COUNTRIES.length)] ?? 'SUI',
      tour,
    });
  }
  return players;
}

/** 128 ATP and 128 WTA players, stable across runs. */
export const ATP_PLAYERS: readonly Player[] = buildTour('ATP', ATP_NAMED, 20260525);
export const WTA_PLAYERS: readonly Player[] = buildTour('WTA', WTA_NAMED, 20260526);
export const ALL_PLAYERS: readonly Player[] = [...ATP_PLAYERS, ...WTA_PLAYERS];

/** The named players are the seeds, in the order listed above. */
export const ATP_SEED_COUNT = ATP_NAMED.length;
export const WTA_SEED_COUNT = WTA_NAMED.length;

export function playersForTour(tour: Tour): readonly Player[] {
  return tour === 'ATP' ? ATP_PLAYERS : WTA_PLAYERS;
}
