"""Building the persistence implementation the app and its scripts run on.

Lives apart from `app.main` so a script can build repositories without
importing the app module, whose module-level `create_app()` seeds the demo game
as a side effect (issue #32).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

from sqlalchemy import inspect
from sqlalchemy.orm import Session, sessionmaker

from app.repositories.interfaces import Repositories
from app.repositories.memory import MemoryRepositories
from app.repositories.models import Base
from app.repositories.sqlalchemy_repos import (
    SqlAlchemyRepositories,
    create_db_engine,
    create_session_factory,
)

#: Opens a `Repositories` for the life of one request and closes it after.
RepositoryScope = Callable[[], AbstractContextManager[Repositories]]


def fixed_scope(repos: Repositories) -> RepositoryScope:
    """One shared instance, for the in-memory set and for injected test doubles."""

    @contextmanager
    def scope() -> Iterator[Repositories]:
        yield repos

    return scope


def _session_scope(session_factory: sessionmaker[Session]) -> RepositoryScope:
    """A fresh session per request.

    A SQLAlchemy Session is not thread-safe, and uvicorn runs sync endpoints in
    a threadpool, so sharing one across requests corrupts results under any
    concurrency at all — it surfaces as an IndexError inside SQLAlchemy's row
    handling rather than as anything that names the real cause. One session per
    request is the standard answer and the only correct one here.
    """

    @contextmanager
    def scope() -> Iterator[Repositories]:
        session = session_factory()
        try:
            yield SqlAlchemyRepositories(session)
        finally:
            session.close()

    return scope


#: `sqlite` is a working alias for `sqlalchemy`: the dialect comes from
#: `DATABASE_URL` alone, never from this setting.
_BACKENDS = {"memory": "memory", "sqlalchemy": "sqlalchemy", "sqlite": "sqlalchemy"}


def build_repository_scope(backend: str | None = None) -> RepositoryScope:
    """Pick a persistence implementation.

    `memory` keeps the in-memory set from step 3; `sqlalchemy` (alias `sqlite`)
    uses SQLAlchemy against whatever `DATABASE_URL` names. The services and the
    domain never learn which one they got.
    """
    choice = backend or os.environ.get("REPOSITORY_BACKEND", "memory")
    if choice not in _BACKENDS:
        raise ValueError(
            f"Unknown REPOSITORY_BACKEND {choice!r}; use 'memory' or 'sqlalchemy' "
            "(or 'sqlite', an alias for 'sqlalchemy')."
        )
    if _BACKENDS[choice] == "memory":
        return fixed_scope(MemoryRepositories())

    engine = create_db_engine()
    # Only SQLite keeps create_all: a throwaway or first-run local database
    # works without migrations. On every other URL (Postgres) Alembic owns the
    # schema, and an unmigrated database stops start-up instead of being
    # silently populated.
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
    else:
        missing = set(Base.metadata.tables) - set(inspect(engine).get_table_names())
        if missing:
            raise RuntimeError(
                f"The database schema is missing tables ({', '.join(sorted(missing))}). "
                "Run `alembic upgrade head` before starting the app."
            )
    return _session_scope(create_session_factory(engine))


def build_repositories(backend: str | None = None) -> Repositories:
    """A single `Repositories` outside a request — for scripts and seeding.

    Holds its session open for the caller's lifetime, which is right for a
    one-shot script and wrong for a server; the server uses the scope above.
    """
    scope = build_repository_scope(backend)
    context = scope()
    return context.__enter__()
