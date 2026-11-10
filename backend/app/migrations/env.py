from alembic import context

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.db import Base, get_engine, include_object

target_metadata = Base.metadata


def run_migrations_online() -> None:
    # Reuse the app's engine so the same URL and SQLite PRAGMAs apply.
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          include_object=include_object, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
