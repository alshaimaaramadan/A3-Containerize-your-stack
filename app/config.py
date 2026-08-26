"""Configuration, read from the environment.

Nothing in this project hard-codes a host, a password or a database name. The
one setting the application needs is DATABASE_URL, and it comes from the
environment: from `.env` when you run uvicorn on your machine, and from
docker-compose when you run the stack.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Loads .env into the environment if the file exists, and — importantly — does
# not overwrite variables that are already set. That ordering is what lets
# docker-compose hand the container a DATABASE_URL pointing at the `db` service
# even though a .env aimed at localhost may also have been copied in.
load_dotenv(override=False)


@dataclass(frozen=True)
class Settings:
    """The environment, read once, as a value rather than scattered os.getenv calls."""

    database_url: str | None

    def require_database_url(self) -> str:
        """Return DATABASE_URL, or fail loudly enough to be fixable.

        Read at startup by the composition root, not at import time by every
        module, so the in-memory repository still runs with no database
        configured at all."""
        if not self.database_url:
            raise RuntimeError(
                "DATABASE_URL is not set. Copy .env.example to .env and fill it "
                "in, or run the stack with `docker compose up`, which sets it "
                "for the api container."
            )
        return self.database_url


settings = Settings(database_url=os.getenv("DATABASE_URL"))
