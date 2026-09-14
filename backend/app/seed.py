"""A realistic demo game.

Step 4's definition of done asks for a seed script; this is it, and step 3 uses
the same function so the API has something to serve. Deterministic: same seed,
same draw, same results, every run.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from app.domain.entities import (
    BetGroup,
    Draw,
    DrawEntry,
    DrawSection,
    OutcomeEntry,
    Participation,
    Player,
    Question,
    Tournament,
    User,
)
from app.domain.enums import (
    AnswerType,
    BetGroupKind,
    BetGroupStatus,
    ParticipationStatus,
    QuestionFamily,
    RoundReached,
    Surface,
    Tour,
    TournamentCategory,
    TournamentStatus,
    TournamentVisibility,
    TypedQuestionKind,
)
from app.repositories.interfaces import Repositories
from app.services.auth import hash_password

SEED = 20260525
SECTIONS = 8
PER_SECTION = 16
SEEDS_PER_DRAW = 32

#: The real players are the seeds, in ranking order.
ATP_NAMED = [
    ("Carlos Alcaraz", "ESP"), ("Jannik Sinner", "ITA"), ("Alexander Zverev", "GER"),
    ("Holger Rune", "DEN"), ("Taylor Fritz", "USA"), ("Novak Djokovic", "SRB"),
    ("Casper Ruud", "NOR"), ("Alex de Miñaur", "AUS"), ("Lorenzo Musetti", "ITA"),
    ("Andrey Rublev", "RUS"), ("Ben Shelton", "USA"), ("Stefanos Tsitsipas", "GRE"),
    ("Jack Draper", "GBR"), ("Frances Tiafoe", "USA"), ("Ugo Humbert", "FRA"),
    ("Tomáš Macháč", "CZE"), ("Sebastian Korda", "USA"), ("Francisco Cerúndolo", "ARG"),
    ("Luciano Darderi", "ITA"), ("Alex Michelsen", "USA"), ("Jakub Menšík", "CZE"),
    ("Arthur Fils", "FRA"), ("Flavio Cobolli", "ITA"), ("Matteo Berrettini", "ITA"),
    ("Grigor Dimitrov", "BUL"), ("Jiří Lehecká", "CZE"), ("Alexander Bublik", "KAZ"),
    ("Alexei Popyrin", "AUS"), ("Tallon Griekspoor", "NED"), ("Sebastián Báez", "ARG"),
    ("Brandon Nakashima", "USA"), ("Jan-Lennard Struff", "GER"),
]

WTA_NAMED = [
    ("Aryna Sabalenka", "BLR"), ("Iga Świątek", "POL"), ("Coco Gauff", "USA"),
    ("Jasmine Paolini", "ITA"), ("Elena Rybakina", "KAZ"), ("Mirra Andreeva", "RUS"),
    ("Jessica Pegula", "USA"), ("Qinwen Zheng", "CHN"), ("Emma Navarro", "USA"),
    ("Daria Kasatkina", "AUS"), ("Paula Badosa", "ESP"), ("Diana Shnaider", "RUS"),
    ("Barbora Krejčíková", "CZE"), ("Karolína Muchová", "CZE"), ("Beatriz Haddad Maia", "BRA"),
    ("Donna Vekić", "CRO"), ("Marta Kostyuk", "UKR"), ("Victoria Azarenka", "BLR"),
    ("Ons Jabeur", "TUN"), ("Elina Svitolina", "UKR"), ("Leylah Fernandez", "CAN"),
    ("Magda Linette", "POL"), ("Clara Tauson", "DEN"), ("Anna Kalinskaya", "RUS"),
    ("Linda Nosková", "CZE"), ("Katie Boulter", "GBR"), ("Sofia Kenin", "USA"),
    ("Caroline Garcia", "FRA"), ("Veronika Kudermetova", "RUS"), ("Yulia Putintseva", "KAZ"),
    ("Camila Osorio", "COL"), ("Lucia Bronzetti", "ITA"),
]

FILLER_FIRST = ["Andres", "Bjorn", "Cedric", "Dario", "Emil", "Gustav", "Hugo", "Ivan",
                "Janek", "Kasper", "Luka", "Milos", "Nuno", "Otto", "Pavel", "Rafa"]
FILLER_FIRST_WTA = ["Adela", "Brigita", "Carla", "Dana", "Elsa", "Frida", "Greta", "Hana",
                    "Ilona", "Jana", "Katia", "Lena", "Mira", "Nela", "Olga", "Petra"]
FILLER_LAST = ["Almeida", "Brandt", "Corradi", "Dvorak", "Engberg", "Ferrer", "Holm",
               "Ivanov", "Jansen", "Kowalski", "Lindqvist", "Moravec", "Novotny", "Olsen",
               "Pereira", "Quintana", "Rossi", "Sandberg", "Toth", "Urban", "Vogel", "Zima"]
FILLER_COUNTRIES = ["ARG", "AUT", "BEL", "BRA", "CHI", "COL", "CRO", "DEN", "FIN", "HUN",
                    "JPN", "KOR", "NOR", "POR", "ROU", "SVK", "SWE", "SUI"]

PARTICIPANT_NAMES = ["Sofia", "Jonas", "Priya", "Tomás", "Anneke", "Marek", "Yusuf",
                     "Claire", "Bea", "Sam", "Lena", "Rui", "Ada"]

DEMO_PASSWORD = "deuce-demo-password"


def _build_players(tour: Tour, named: list[tuple[str, str]], rng: random.Random) -> list[Player]:
    players = [
        Player(id=f"{tour.lower()}-p{i + 1}", full_name=name, country_code=country, tour=tour)
        for i, (name, country) in enumerate(named)
    ]
    first_names = FILLER_FIRST if tour is Tour.ATP else FILLER_FIRST_WTA
    used = {p.full_name for p in players}
    index = len(players)
    while len(players) < SECTIONS * PER_SECTION:
        full_name = f"{rng.choice(first_names)} {rng.choice(FILLER_LAST)}"
        if full_name in used:
            continue
        used.add(full_name)
        index += 1
        players.append(
            Player(
                id=f"{tour.lower()}-p{index}",
                full_name=full_name,
                country_code=rng.choice(FILLER_COUNTRIES),
                tour=tour,
            )
        )
    return players


def seed_demo_game(repos: Repositories) -> str:
    """Populate a two-draw Grand Slam at the quarter-final stage. Returns its id."""
    rng = random.Random(SEED)
    now = datetime.now(UTC)

    organiser = User(
        id="user-admin", email="organiser@example.com",
        password_hash=hash_password(DEMO_PASSWORD), display_name="The organiser",
        full_name="Hélène Moreau", is_admin=True, is_active=True,
        email_verified_at=now - timedelta(days=400), created_at=now - timedelta(days=400),
    )
    repos.users.add(organiser)

    participants = [
        User(
            id="user-1", email="you@example.com", password_hash=hash_password(DEMO_PASSWORD),
            display_name="You", full_name="Mattia Ricci", is_admin=False, is_active=True,
            email_verified_at=now - timedelta(days=200), created_at=now - timedelta(days=240),
        )
    ]
    for index, name in enumerate(PARTICIPANT_NAMES, start=2):
        participants.append(
            User(
                id=f"user-{index}", email=f"{name.lower()}@example.com",
                password_hash=hash_password(DEMO_PASSWORD), display_name=name, full_name=None,
                is_admin=False, is_active=True,
                email_verified_at=now - timedelta(days=200),
                created_at=now - timedelta(days=240),
            )
        )
    for user in participants:
        repos.users.add(user)

    tournament = Tournament(
        id="roland-garros-2026", name="Roland-Garros 2026",
        category=TournamentCategory.GRAND_SLAM, surface=Surface.CLAY, location="Paris, France",
        start_date=(now - timedelta(days=10)).date(), end_date=(now + timedelta(days=4)).date(),
        signup_deadline=now - timedelta(days=11), visibility=TournamentVisibility.PUBLIC,
        join_code=None, status=TournamentStatus.RUNNING,
        rules_markdown="Deadlines are the deadlines.", created_at=now - timedelta(days=70),
    )
    repos.tournaments.add(tournament)

    upcoming = Tournament(
        id="wimbledon-2026", name="Wimbledon 2026",
        category=TournamentCategory.GRAND_SLAM, surface=Surface.GRASS,
        location="London, United Kingdom",
        start_date=(now + timedelta(days=25)).date(), end_date=(now + timedelta(days=38)).date(),
        signup_deadline=now + timedelta(days=18), visibility=TournamentVisibility.PUBLIC,
        join_code=None, status=TournamentStatus.PUBLISHED,
        rules_markdown="Same rules, shorter grass.", created_at=now - timedelta(days=30),
    )
    repos.tournaments.add(upcoming)

    for tour, named in ((Tour.ATP, ATP_NAMED), (Tour.WTA, WTA_NAMED)):
        players = _build_players(tour, named, rng)
        for player in players:
            repos.players.add(player)

        draw = Draw(
            id=f"rg-{tour.lower()}", tournament_id=tournament.id, tour=tour,
            draw_size=SECTIONS * PER_SECTION, best_of=5 if tour is Tour.ATP else 3,
            official_draw_url="https://www.rolandgarros.com/en-us/draws",
        )
        repos.draws.add(draw)

        seeded = players[:SEEDS_PER_DRAW]
        unseeded = players[SEEDS_PER_DRAW:]
        rng.shuffle(unseeded)
        cursor = 0

        for section_index in range(1, SECTIONS + 1):
            section = DrawSection(
                id=f"{draw.id}-section-{section_index}", draw_id=draw.id, index=section_index
            )
            repos.draws.add_section(section)

            section_players: list[tuple[Player, int | None]] = []
            # Seeds are placed one per section per pass, the way a real draw does it.
            for pass_index in range(SEEDS_PER_DRAW // SECTIONS):
                seed_number = pass_index * SECTIONS + section_index
                section_players.append((seeded[seed_number - 1], seed_number))
            while len(section_players) < PER_SECTION:
                section_players.append((unseeded[cursor], None))
                cursor += 1

            for player, seed_number in section_players:
                repos.draws.add_entry(
                    DrawEntry(
                        id=f"{draw.id}-e-{player.id}", draw_id=draw.id,
                        section_id=section.id, player_id=player.id, seed=seed_number,
                    )
                )

            # One quarter-finalist per section; the rest are eliminated in order.
            if rng.random() < 0.66:
                winner = section_players[0][0]
            else:
                winner = rng.choice(section_players)[0]
            rest = [p for p, _ in section_players if p.id != winner.id]
            rng.shuffle(rest)
            losers = [(RoundReached.R128, 8), (RoundReached.R64, 4),
                      (RoundReached.R32, 2), (RoundReached.R16, 1)]
            position = 0
            rows: list[OutcomeEntry] = []
            for round_reached, count in losers:
                for _ in range(count):
                    if position < len(rest):
                        rows.append(
                            OutcomeEntry(draw.id, rest[position].id, round_reached, None)
                        )
                        position += 1

            rows.append(OutcomeEntry(draw.id, winner.id, RoundReached.QF, None))
            repos.outcomes.add_many(rows)

    for index, user in enumerate(participants, start=1):
        repos.participations.add(
            Participation(
                id=f"part-{index}", user_id=user.id, tournament_id=tournament.id,
                joined_at=now - timedelta(days=18), status=ParticipationStatus.ACTIVE,
            )
        )

    _seed_bet_groups(repos, tournament.id, now)
    repos.commit()
    return tournament.id


def _seed_bet_groups(repos: Repositories, tournament_id: str, now: datetime) -> None:
    groups = [
        BetGroup(
            id="rg-bg-tournament", tournament_id=tournament_id, kind=BetGroupKind.TOURNAMENT,
            round=None, title="Tournament bets",
            intro_markdown="Submitted once per draw, before a ball is struck.",
            deadline=now - timedelta(days=10), status=BetGroupStatus.SETTLED,
        ),
        BetGroup(
            id="rg-bg-qf", tournament_id=tournament_id, kind=BetGroupKind.ROUND, round=5,
            title="Quarter-finals",
            intro_markdown="Quarters on both sides this week.",
            deadline=now + timedelta(hours=5), status=BetGroupStatus.OPEN,
        ),
    ]
    for group in groups:
        repos.bet_groups.add(group)

    typed = [
        (TypedQuestionKind.QF_PICKS, "Quarter-finalists — one per section", "1 pt each"),
        (TypedQuestionKind.SF_PICKS, "Semi-finalists — four of your eight", "2 pts each"),
        (TypedQuestionKind.FINALIST_PICKS, "Finalists — two of your four", "3 pts each"),
        (TypedQuestionKind.CHAMPION, "Champion — one of your two finalists", "5 pts"),
        (TypedQuestionKind.UNDERPERFORMER, "Underperformer — a top-ten seed", "3 / 2 / 1"),
        (TypedQuestionKind.BREAKOUT, "Breakout — an unseeded runner", "2 / 3 / 4 / 5 / 7"),
    ]
    position = 0
    for draw_id in ("rg-atp", "rg-wta"):
        for kind, prompt, hint in typed:
            repos.questions.add(
                Question(
                    id=f"rg-bg-tournament-{draw_id}-{kind.lower()}",
                    bet_group_id="rg-bg-tournament", draw_id=draw_id,
                    family=QuestionFamily.TYPED, kind=kind, prompt=prompt,
                    answer_type=AnswerType.PLAYER, options=None, matchup=None,
                    points_hint=hint, deadline_override=None, position=position,
                )
            )
            position += 1

    # The open group needs answerable questions, and a featured tie has to be
    # between two players who actually reached this round.
    for draw_id in ("rg-atp", "rg-wta"):
        reached = [
            o.player_id
            for o in repos.outcomes.list_for_draw(draw_id)
            if o.round_reached is RoundReached.QF
        ]
        if len(reached) < 2:
            continue
        repos.questions.add(
            Question(
                id=f"rg-bg-qf-{draw_id}-featured",
                bet_group_id="rg-bg-qf",
                draw_id=draw_id,
                family=QuestionFamily.GENERIC,
                kind=None,
                prompt=f"Featured match — {draw_id.split('-')[1].upper()}",
                answer_type=AnswerType.MATCH_RESULT,
                options=None,
                matchup=(reached[0], reached[1]),
                points_hint="1 + 1 pt",
                deadline_override=None,
                position=0,
            )
        )
