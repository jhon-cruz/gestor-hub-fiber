"""Create the isolated integration-test database when it does not exist."""

import os

import psycopg
from psycopg import sql


def main() -> None:
    database_name = os.environ.get("POSTGRES_TEST_DATABASE", "gestor_hub_fiber_test")
    admin_url = os.environ["TEST_ADMIN_DATABASE_URL"]
    with psycopg.connect(admin_url, autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)
        ).fetchone()
        if exists is None:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))


if __name__ == "__main__":
    main()
