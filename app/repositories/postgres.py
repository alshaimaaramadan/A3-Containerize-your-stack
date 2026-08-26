"""The same interface, backed by Postgres.

This is the only file in the project that contains SQL, knows what a connection
is, or would notice if the database moved. Compare it with memory.py: the method
names, arguments and return types are identical, because the service calls both
through app/repositories/base.py and cannot tell them apart.
"""

from __future__ import annotations

from typing import Optional

from psycopg.rows import class_row
from psycopg_pool import ConnectionPool

from app.models import Task
from app.repositories.base import TaskRepository
from app.seed import SEED_TASKS

# Every query selects exactly the columns Task is made of, in that order, so
# psycopg can build the model straight from the row.
COLUMNS = "id, title, done"


def _like_pattern(text: str) -> str:
    """Turn user text into a safe ILIKE pattern.

    The value is already sent as a bound parameter, so this is not about SQL
    injection — it is about meaning. Without escaping, a search for "50%" would
    reach ILIKE as a wildcard and match everything, and "_" would match any
    single character. The user typed characters, not a pattern."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class PostgresTaskRepository(TaskRepository):
    """Tasks in a `tasks` table, reached through a small connection pool."""

    def __init__(self, dsn: str, *, connect_timeout: float = 30.0) -> None:
        self._connect_timeout = connect_timeout
        # open=False: building the object must not reach out to the network.
        # The pool is opened in open(), during application startup, where a
        # failure can be reported properly instead of blowing up an import.
        #
        # check=check_connection matters more than it looks. Restart the
        # database container and every connection sitting idle in the pool is
        # dead; without this the next request would be handed one and fail. With
        # it, the pool tests a connection before lending it and quietly replaces
        # the broken ones — which is why the API survives a restart of the
        # database container rather than needing a restart of its own.
        self._pool = ConnectionPool(
            conninfo=dsn,
            min_size=1,
            max_size=10,
            open=False,
            check=ConnectionPool.check_connection,
        )

    # -- lifecycle -----------------------------------------------------------

    def open(self) -> None:
        """Open the pool and wait until the database actually answers.

        compose already holds the api container back until Postgres reports
        healthy; the timeout is the belt to that pair of braces, for when the
        app is started by hand against a database that is still booting."""
        self._pool.open(wait=True, timeout=self._connect_timeout)

    def close(self) -> None:
        self._pool.close()

    # -- queries -------------------------------------------------------------

    def list_tasks(
        self, done: Optional[bool] = None, search: Optional[str] = None
    ) -> list[Task]:
        # Filtering happens in SQL, not in Python. The list version had to load
        # everything and throw most of it away; Postgres reads only what matches.
        conditions: list[str] = []
        params: list[object] = []

        if done is not None:
            conditions.append("done = %s")
            params.append(done)

        if search is not None:
            # ILIKE is the case-insensitive LIKE — the SQL spelling of the
            # `needle in title.lower()` the in-memory version does.
            conditions.append("title ILIKE %s")
            params.append(_like_pattern(search.strip()))

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        # ORDER BY id because a table has no natural order. Without it Postgres
        # may return rows in any order it likes, and "the list came back
        # shuffled after an update" is a horrible bug to chase.
        sql = f"SELECT {COLUMNS} FROM tasks{where} ORDER BY id"

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Task)) as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def get(self, task_id: int) -> Optional[Task]:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Task)) as cur:
                cur.execute(f"SELECT {COLUMNS} FROM tasks WHERE id = %s", (task_id,))
                return cur.fetchone()

    def counts(self) -> tuple[int, int]:
        # One round trip, no rows transferred, no counting in Python.
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE done) FROM tasks")
                total, done = cur.fetchone()
                return int(total), int(done)

    # -- commands ------------------------------------------------------------

    def add(self, title: str) -> Task:
        # RETURNING gives back the row Postgres actually wrote — including the
        # id the sequence chose — so there is no second query and no guessing.
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Task)) as cur:
                cur.execute(
                    f"INSERT INTO tasks (title, done) VALUES (%s, FALSE) "
                    f"RETURNING {COLUMNS}",
                    (title,),
                )
                return cur.fetchone()

    def update(
        self, task_id: int, title: Optional[str] = None, done: Optional[bool] = None
    ) -> Optional[Task]:
        assignments: list[str] = []
        params: list[object] = []

        if title is not None:
            assignments.append("title = %s")
            params.append(title)

        if done is not None:
            assignments.append("done = %s")
            params.append(done)

        # The service rejects an empty update before it gets here, but a
        # repository that built "SET  WHERE" from an empty list would be a
        # syntax error waiting for the day someone calls it directly.
        if not assignments:
            return self.get(task_id)

        params.append(task_id)
        sql = (
            f"UPDATE tasks SET {', '.join(assignments)} "
            f"WHERE id = %s RETURNING {COLUMNS}"
        )

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=class_row(Task)) as cur:
                cur.execute(sql, params)
                # None here means no row matched, which is the caller's 404.
                return cur.fetchone()

    def delete(self, task_id: int) -> bool:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
                return cur.rowcount == 1

    def reset(self) -> list[Task]:
        # One transaction: either the table is emptied and reseeded, or nothing
        # happened. There is no moment a client can observe an empty task list.
        # TRUNCATE ... RESTART IDENTITY also rewinds the id sequence, so the
        # seed tasks come back as 1, 2, 3 rather than continuing to climb.
        with self._pool.connection() as conn:
            with conn.transaction():
                with conn.cursor(row_factory=class_row(Task)) as cur:
                    cur.execute("TRUNCATE tasks RESTART IDENTITY")
                    cur.executemany(
                        "INSERT INTO tasks (title, done) VALUES (%s, %s)",
                        SEED_TASKS,
                    )
                    cur.execute(f"SELECT {COLUMNS} FROM tasks ORDER BY id")
                    return cur.fetchall()
