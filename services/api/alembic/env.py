"""Alembic environment bound to the validated application database URL."""

import time
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import OperationalError

from alembic import context
from app import models  # noqa: F401
from app.core.config import get_settings
from app.core.database import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    connection = None
    for attempt in range(1, 11):
        try:
            connection = connectable.connect()
            break
        except OperationalError:
            if attempt == 10:
                raise
            time.sleep(2)

    assert connection is not None
    with connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
