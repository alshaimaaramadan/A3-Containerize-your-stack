# Task API — now with a database

The same to-do list API as before, with one thing changed: tasks are no longer a Python list that
dies with the process. They are rows in **Postgres**, running in Docker with a named volume, and
the whole stack — app and database — starts with one command:

```bash
docker compose up
```

Built for FlyRank Week 3, Assignment 3 (BE-04). The previous version is
[Week 2's Task API](../../WEEK%202%20-%20CRUD%20API).

---

## Contents

- [What changed, honestly](#what-changed-honestly)
- [Run it](#run-it)
- [How the pieces fit](#how-the-pieces-fit)
- [The swap: one line, one file](#the-swap-one-line-one-file)
- [Configuration and secrets](#configuration-and-secrets)
- [The schema](#the-schema)
- [Proving persistence](#proving-persistence)
- [Endpoints](#endpoints)
- [Troubleshooting](#troubleshooting)

---

## What changed, honestly

The assignment says the payoff of the previous week's layering is that "switch storage" changes
only one file. Here is the honest version of that claim, because it comes with an asterisk.

**The previous version had no layers.** It was a single `main.py`: FastAPI routes with the task
list, the filtering and the validation all in the same functions. There was no repository to
replace, and no interface to replace it behind.

So this assignment did two things, and it is worth keeping them apart:

1. **First, the layering was created.** `main.py` was split into `routes` → `service` →
   `repository`, with the old Python list moved behind a `TaskRepository` interface as
   `InMemoryTaskRepository`. This was a refactor with no behaviour change — the endpoints,
   status codes and error messages all stayed the same, and a
   [42-check smoke test](#a-note-on-how-this-was-checked) against the in-memory repository confirms it.
2. **Then the storage was switched.** `PostgresTaskRepository` was written against the same
   interface, and the composition root was pointed at it.

Step 2 is the one the assignment is about, and for step 2 the claim holds exactly:

| File | Changed in step 2? |
|---|---|
| `app/routes.py` | No |
| `app/service.py` | No |
| `app/models.py` | No |
| `app/errors.py` | No |
| `app/repositories/base.py` | No |
| `app/repositories/postgres.py` | **New file** |
| `app/main.py` | **One line** — which class to construct |

Neither `app/service.py` nor `app/routes.py` contains a SQL keyword, a connection, a cursor or a
driver import; `routes.py` does not import from `app/repositories/` at all, and `service.py`
imports only the interface. Every mention of Postgres in either file is in a comment saying so.
That is not a claim to take on faith — check it:

```bash
grep -nE "psycopg|SELECT|INSERT|UPDATE |cursor|conninfo" app/service.py app/routes.py   # no hits
grep -n  "^from app.repositories" app/service.py app/routes.py   # only base.py, only in service
```

Even `GET /` was made to stay quiet about it. An earlier draft had the root endpoint return
`"storage": "postgres"`, which was a small lie about the architecture: a route that names the
database is a route you have to edit when the database changes. It came out.

What this does *not* prove is that a layering you inherit will always survive a real swap
untouched. It survived here because the interface was designed one commit before the swap, with
the swap in mind. The genuinely useful part is smaller and still true: **the seam is what makes the
change cheap**, and the seam has to exist before you need it.

---

## Run it

You need **Docker Desktop** (or Docker Engine + the Compose plugin). Nothing else — no Python, no
Postgres installed on your machine.

```bash
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
docker compose up
```

That single command:

1. builds the API image from the `Dockerfile`,
2. starts Postgres 16 with a named volume for its data,
3. runs `db/init/001_schema.sql` to create the `tasks` table — **on the first start only**,
4. waits until Postgres actually answers (`pg_isready`), *then* starts the API,
5. serves the API on **http://localhost:8000**, docs at **http://localhost:8000/docs**.

Useful variations:

```bash
docker compose up -d          # in the background
docker compose logs -f api    # follow the API's logs
docker compose ps             # is everything healthy?
docker compose down           # stop and remove containers — the volume, and your data, stay
docker compose down -v        # ...and delete the volume too. This throws the data away.
```

### Running the app outside Docker

Sometimes you want the app on your machine with `--reload`, and only the database in a container:

```bash
docker compose up -d db                                   # database only
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt             # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --reload
```

This is the case the `DATABASE_URL` in `.env` is written for — it points at `localhost:5432`,
which is where compose publishes the database. Inside the stack the app gets a different
`DATABASE_URL`, pointing at `db`. See [Configuration and secrets](#configuration-and-secrets).

---

## How the pieces fit

```
                       HTTP
                        │
   app/main.py ─────────┼── assembles everything; the only file that names a
   (composition root)   │   concrete repository
                        ▼
   app/routes.py            paths, status codes, Swagger docs.
        │                   Does no work of its own.
        ▼
   app/service.py           the rules: blank titles, 404 before 400,
        │                   what /stats means. No HTTP, no SQL.
        ▼
   app/repositories/base.py     the interface. The service knows nothing else.
        │
        ├── memory.py            a Python list        (the old storage, kept for comparison)
        └── postgres.py          SQL + a connection pool   ← in use
```

Reading it as a rule: **each layer knows only the one below it, through an interface.** The
service cannot see SQL. The routes cannot see storage at all. The repository cannot see HTTP —
`postgres.py` does not import FastAPI, and `service.py` raises plain Python exceptions
(`TaskNotFound`, `InvalidTask`) that `main.py` alone translates into 404 and 400.

| File | What it is for |
|---|---|
| `app/main.py` | Builds the app: picks the repository, opens it at startup, registers error handlers |
| `app/routes.py` | The HTTP layer — one function per endpoint |
| `app/service.py` | The rules, framework-free |
| `app/repositories/base.py` | The `TaskRepository` interface — the seam |
| `app/repositories/postgres.py` | The SQL. **The only file in the project that contains any** |
| `app/repositories/memory.py` | The old list-backed storage, still working, unused |
| `app/models.py` | Request and response shapes (Pydantic) |
| `app/errors.py` | `TaskNotFound`, `InvalidTask` — domain errors with no HTTP in them |
| `app/config.py` | Reads `DATABASE_URL` from the environment / `.env` |
| `app/dependencies.py` | How a route gets the service without importing the wiring |
| `app/seed.py` | The three starting tasks, in one place |
| `db/init/001_schema.sql` | The whole schema, in one file |
| `scripts/smoke_test.py` | 42 endpoint checks, run against the in-memory repository |
| `Dockerfile` | The API image |
| `docker-compose.yml` | App + database, started together |

---

## The swap: one line, one file

All of `app/main.py` that concerns storage:

```python
# THE SWAP. One line, one file. Tasks used to live in a Python list:
#
#     from app.repositories.memory import InMemoryTaskRepository
#     repository: TaskRepository = InMemoryTaskRepository()
#
# and now they live in Postgres:

repository: TaskRepository = PostgresTaskRepository(settings.require_database_url())
```

Uncomment the two lines in the comment, delete the line below them, and the API runs on the Python
list again — every endpoint, every status code, every error message identical. It just forgets
everything when you stop it.

The interface both classes implement is nine methods (`app/repositories/base.py`):

```python
open()   close()                          # lifecycle: a pool needs opening, a list does not
list_tasks(done=None, search=None)        # filtering lives here — WHERE clause or comprehension
get(task_id)      counts()
add(title)        update(task_id, ...)    delete(task_id)     reset()
```

Two details worth pointing at, because they are where the two implementations genuinely differ
and the service still cannot tell:

- **Filtering** happens inside the repository, not the service. The list version loads everything
  and throws most of it away; the Postgres version writes a `WHERE` clause and reads only what
  matches. Same method signature, same results, very different amount of work.
- **Id assignment** moved from the application to the database. The list version computed
  `max(id) + 1`, which two simultaneous requests could get wrong; Postgres uses an identity
  sequence, which they cannot.

---

## Configuration and secrets

`.env` is **gitignored**. `.env.example` is committed, with the same keys and placeholder values,
so a fresh checkout tells you exactly what to fill in:

```bash
cp .env.example .env
```

| Variable | Used by | What it is |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | compose | Creates the database on first start; also builds the app's connection string |
| `POSTGRES_PORT` | compose | Host port for Postgres (default `5432`) |
| `APP_PORT` | compose | Host port for the API (default `8000`) |
| `DATABASE_URL` | the app | The one setting the application code itself reads |

### The `localhost` trap, and why there are two `DATABASE_URL`s

This is the part that catches people, so it is worth being explicit.

The `DATABASE_URL` in `.env` says `@localhost:5432`. That is correct **for a process running on
your machine**. It is wrong inside a container, because `localhost` in a container means *that
container* — the API would look for Postgres inside itself and find nothing.

So `docker-compose.yml` sets the API container's `DATABASE_URL` itself, from the same `.env`
values, with the right host:

```yaml
environment:
  DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
```

`db` is the service name, and Docker's internal DNS resolves it on the compose network. The two
URLs are the same database reached from two different places.

`app/config.py` calls `load_dotenv(override=False)`, so a variable already present in the
environment always wins over the `.env` file. That ordering is what makes this safe: even if a
`.env` aimed at `localhost` ends up next to the app, the value compose set is the one used.

One gotcha inherited from the format: `DATABASE_URL` is a URL, so a raw `@`, `:` or `/` in the
password is parsed as structure. Keep the local password alphanumeric, or percent-encode it.

---

## The schema

One file, `db/init/001_schema.sql`. Compose mounts `db/init/` at
`/docker-entrypoint-initdb.d`, and the official Postgres image runs everything in it **once** —
the first time the data directory is empty. On every later start the volume already holds a
database and the file is skipped, which is the persistence working as intended, not a bug.

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id    INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    title TEXT    NOT NULL CHECK (btrim(title) <> ''),
    done  BOOLEAN NOT NULL DEFAULT FALSE
);
```

- `GENERATED BY DEFAULT AS IDENTITY` — not `ALWAYS` — so the seed rows can claim ids 1, 2 and 3
  explicitly while ordinary inserts still take theirs from the sequence. The file then calls
  `setval` to push the sequence past the highest seeded id; without that, the very first
  `POST /tasks` would collide on the primary key.
- The `CHECK` repeats a rule the service already enforces. That is deliberate: the service
  protects the API, the constraint protects the *data*, from `psql`, from a migration, from a
  second application written later.
- The seed insert is guarded by `WHERE NOT EXISTS (SELECT 1 FROM tasks)`, and every statement uses
  `IF NOT EXISTS`, so the file is safe to apply by hand against a database that already exists:

  ```bash
  docker compose exec -T db psql -U taskapi -d taskapi < db/init/001_schema.sql
  ```

To look at the data directly:

```bash
docker compose exec db psql -U taskapi -d taskapi -c "SELECT * FROM tasks ORDER BY id;"
```

---

## Proving persistence

> **Status: run, and the output below is what it printed.** Executed end to end on 2026-08-26
> against Docker 29.7.2 / Compose v5.4.0 on Windows 11, starting from `docker compose down -v` so
> the first step really was a cold start. Every block below is pasted from that run rather than
> written from expectation — see [A note on how this was checked](#a-note-on-how-this-was-checked).

The claim to test is not "the database saves things". It is: **the data outlives both containers.**
So the test restarts the app, then destroys and recreates the containers, and then — as a control —
deletes the volume to show that the volume is what was doing the work.

Commands below use `curl.exe` because in PowerShell bare `curl` is an alias for
`Invoke-WebRequest`. On macOS/Linux use plain `curl` and single quotes for the JSON body.

**1. Start the stack and look at the seed data**

```bash
docker compose up -d
curl.exe http://localhost:8000/tasks
```

```json
[{"id":1,"title":"Read the assignment","done":true},{"id":2,"title":"Build the API","done":false},{"id":3,"title":"Write the README","done":false}]
```

The three seed tasks, ids 1-3 — inserted by `001_schema.sql`, which ran because the volume was
brand new and the data directory was empty.

**2. Create a row of your own**

```bash
curl.exe -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d "{\"title\":\"Survive the restart\"}"
```

```json
{"id":4,"title":"Survive the restart","done":false}
```

Status `201`. Note the id: `4`, not a duplicate of `1`. That is the `setval` at the bottom of
`001_schema.sql` doing its job — the three seed rows claimed their ids explicitly and left the
identity sequence still pointing at 1, and without that nudge this first POST would have failed on
a duplicate primary key.

**3. Restart the app container only** — this is the test the old version failed

```bash
docker compose restart api
curl.exe http://localhost:8000/tasks
```

```json
[{"id":1,"title":"Read the assignment","done":true},{"id":2,"title":"Build the API","done":false},{"id":3,"title":"Write the README","done":false},{"id":4,"title":"Survive the restart","done":false}]
```

All four. The list-backed version came back with three, because the list lived in the process that
had just been replaced.

**4. Destroy both containers and bring them back**

`down` removes the containers entirely — not a restart, a delete. The named volume survives it.

```bash
docker compose down
docker compose ps -a            # nothing left running
docker volume ls                # taskapi_pgdata is still there
docker compose up -d
curl.exe http://localhost:8000/tasks
```

```
$ docker compose ps -a
NAME      IMAGE     COMMAND   SERVICE   CREATED   STATUS    PORTS

$ docker volume ls
DRIVER    VOLUME NAME
local     taskapi_pgdata
```

Nothing running, and the volume still there. After `up -d`:

```json
[{"id":1,"title":"Read the assignment","done":true},{"id":2,"title":"Build the API","done":false},{"id":3,"title":"Write the README","done":false},{"id":4,"title":"Survive the restart","done":false}]
```

All four tasks, served by a database process that did not exist a moment earlier. The db log for
this boot says `Database directory appears to contain a database; Skipping initialization` — the
schema file was not re-run, and these rows are the ones written before the containers were
deleted.

**5. Confirm it is really on disk, not in the app**

```bash
docker compose exec db psql -U taskapi -d taskapi -c "SELECT id, title, done FROM tasks ORDER BY id;"
```

```
 id |        title        | done
----+---------------------+------
  1 | Read the assignment | t
  2 | Build the API       | f
  3 | Write the README    | f
  4 | Survive the restart | f
(4 rows)
```

The same four rows, read out of Postgres directly, with the API not involved.

**6. The control: delete the volume and watch the data go**

This is the step that proves the volume was responsible, rather than something else quietly
holding state.

```bash
docker compose down -v          # -v deletes the named volume
docker compose up -d
curl.exe http://localhost:8000/tasks
```

```json
[{"id":1,"title":"Read the assignment","done":true},{"id":2,"title":"Build the API","done":false},{"id":3,"title":"Write the README","done":false}]
```

Three seed tasks. "Survive the restart" is gone, because the volume it lived on is gone, and an
empty data directory made Postgres run `001_schema.sql` again. This is the step that rules out
something else quietly holding the state: remove the volume and the data goes with it.

### A note on how this was checked

Both halves have now been checked, by different means:

| What | How | Result |
|---|---|---|
| Routes, service, error shapes, filtering, id handling, OpenAPI | 42 assertions against the API through `TestClient`, with `InMemoryTaskRepository` swapped in exactly the way `main.py` documents | **All pass** |
| That the swap is really a swap | The same test suite drives the app through the same routes and service with the other repository behind them | **All pass** |
| SQL, the schema, the container build, persistence | The six-step procedure above, run end to end on Docker 29.7.2 / Compose v5.4.0; plus every endpoint exercised by hand against the containerised stack | **All pass** |
| That the `CHECK` constraint is real | `INSERT INTO tasks (title) VALUES ('   ');` straight through `psql`, bypassing the API entirely | **Rejected**, as intended |

Run it yourself — no Docker and no database needed, because it uses the in-memory repository:

```bash
.venv/Scripts/pip install -r requirements-dev.txt      # macOS/Linux: .venv/bin/pip
.venv/Scripts/python scripts/smoke_test.py             # prints 42 checks, exits non-zero on failure
```

It is a plain script rather than a pytest suite on purpose: it is here to back up a claim in this
README, and it should be runnable with nothing installed but the app's own dependencies plus
`httpx`.

---

## Endpoints

Unchanged from the previous version — same paths, same status codes, same error shape. Only the
storage underneath is different.

| Method | Path | What it does | Success | Errors |
|---|---|---|---|---|
| `GET` | `/` | API name, version, storage, and where to go next | `200` | — |
| `GET` | `/health` | Liveness check — also what Docker's `HEALTHCHECK` polls | `200` | — |
| `GET` | `/tasks` | List every task | `200` | — |
| `GET` | `/tasks?done=true` | Only finished tasks (`false` for unfinished) | `200` | — |
| `GET` | `/tasks?search=milk` | Titles containing this text, case-insensitive | `200` | — |
| `GET` | `/tasks/{id}` | Get one task by id | `200` | `404` unknown id |
| `POST` | `/tasks` | Create a task from `{"title": "..."}` | `201` | `400` missing or empty title |
| `PUT` | `/tasks/{id}` | Update `title`, `done`, or both | `200` | `404` unknown id · `400` empty body |
| `DELETE` | `/tasks/{id}` | Delete a task | `204` (no body) | `404` unknown id |
| `GET` | `/stats` | Counts: total, done, open | `200` | — |
| `POST` | `/reset` | Restore the three seed tasks — **now really deletes rows** | `200` | — |

A task:

```json
{ "id": 1, "title": "Read the assignment", "done": true }
```

Every error, including a 404 for an unknown path:

```json
{ "error": "Task 99 not found" }
```

The filters compose: `?done=false&search=milk` means "unfinished tasks about milk". An empty list
is a valid answer — it means "nothing matched", which is a different thing from "that task does
not exist".

---

## Troubleshooting

**`bind: address already in use` on 5432** — something else, probably a Postgres you installed
natively, already holds the port. Change `POSTGRES_PORT` in `.env` to `5433`; the app is
unaffected, since inside the stack it talks to `db:5432` directly.

**The API exits with `DATABASE_URL is not set`** — there is no `.env`. Copy `.env.example`.

**Schema changes do not appear** — `db/init/` runs only when the data directory is empty. Either
apply the file by hand (`docker compose exec -T db psql -U taskapi -d taskapi < db/init/001_schema.sql`)
or start over with `docker compose down -v`, which deletes the data.

**`docker compose up` says a variable is not set** — `.env` is missing a key. `docker compose config`
prints the fully substituted file and will point at it.

**The API cannot reach the database after you restarted the database alone** — it should recover on
its own. The connection pool is built with `check=ConnectionPool.check_connection`, so it tests a
connection before lending it out and quietly replaces the ones that died with the old container.
If it does not, `docker compose logs api` will say why.
