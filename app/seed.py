"""The three starting tasks.

Both repositories build their starting state and their POST /reset from this
one list. `db/init/001_schema.sql` states the same three rows a second time,
in SQL, because the database is created by Postgres before any Python runs —
if you change them here, change them there too.
"""

SEED_TASKS: list[tuple[str, bool]] = [
    ("Read the assignment", True),
    ("Build the API", False),
    ("Write the README", False),
]
