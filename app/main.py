"""The composition root: where the application is assembled and started.

This is the only file that names a concrete repository. Everything else —
routes, service, models — is written against the TaskRepository interface, so
this is the only file that had to change when the tasks moved out of a Python
list and into Postgres. Look for the marked line below; that is the whole swap.

Run it with:
    docker compose up                                  # app + database together
    .venv/Scripts/python -m uvicorn app.main:app       # against a database you started yourself
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from app.config import settings
from app.errors import InvalidTask, TaskNotFound
from app.repositories.base import TaskRepository
from app.repositories.postgres import PostgresTaskRepository
from app.routes import router
from app.service import TaskService

# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------
# THE SWAP. One line, one file. Tasks used to live in a Python list:
#
#     from app.repositories.memory import InMemoryTaskRepository
#     repository: TaskRepository = InMemoryTaskRepository()
#
# and now they live in Postgres:

repository: TaskRepository = PostgresTaskRepository(settings.require_database_url())

# Put the old line back and the API still works, endpoint for endpoint — it just
# forgets everything when the process stops. app/service.py and app/routes.py do
# not mention either class and did not change.


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open storage before the first request, close it after the last.

    The in-memory repository has nothing to open, and says so with a no-op; the
    Postgres one opens its connection pool and waits for the database to answer.
    This function does not know or care which of the two it is holding."""
    repository.open()
    app.state.service = TaskService(repository)
    yield
    repository.close()


app = FastAPI(
    title="Task API",
    version="2.0",
    lifespan=lifespan,
    description=(
        "A tiny to-do list API, built as an exercise in CRUD over HTTP.\n\n"
        "Tasks are rows in **Postgres**, running in a Docker container with a "
        "named volume, so they **survive a restart of the app and of the "
        "database**. The previous version kept them in a Python list and lost "
        "them on every restart; the service and the routes are unchanged "
        "between the two — only the repository was replaced."
    ),
    openapi_tags=[
        {"name": "meta", "description": "What this API is, and whether it is alive."},
        {"name": "tasks", "description": "Create, read, update and delete tasks."},
    ],
)

app.include_router(router)


# --------------------------------------------------------------------------
# Error shape
# --------------------------------------------------------------------------
# By default FastAPI reports errors as {"detail": "..."}. This API is specified
# to use {"error": "..."} instead. The service raises framework-free exceptions
# (TaskNotFound, InvalidTask); the two handlers below are the only place in the
# project that decides which HTTP status each one deserves.


@app.exception_handler(TaskNotFound)
def task_not_found_handler(request: Request, exc: TaskNotFound):
    return JSONResponse(status_code=404, content={"error": exc.message})


@app.exception_handler(InvalidTask)
def invalid_task_handler(request: Request, exc: InvalidTask):
    return JSONResponse(status_code=400, content={"error": exc.message})


@app.exception_handler(StarletteHTTPException)
def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Catch the errors the framework raises on its own — an unknown path, a
    wrong method — so that every error this API returns has the same shape.

    Registered against Starlette's HTTPException rather than FastAPI's subclass
    on purpose: handler lookup walks the exception's class hierarchy upward, so
    registering the subclass would miss the plain 404 Starlette raises for an
    unrouted path, and that one error would come back as {"detail": ...}."""
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Catch bodies so malformed that Pydantic rejects them before our code
    runs — a JSON syntax error, or `title` sent as a list. FastAPI's default is
    422; a bad request from the client is a 400 as far as this API is
    concerned, and it should look like every other error it returns."""
    return JSONResponse(status_code=400, content={"error": "Invalid request body"})


# --------------------------------------------------------------------------
# Documentation accuracy
# --------------------------------------------------------------------------


def custom_openapi():
    """Remove the 422 responses FastAPI documents automatically.

    FastAPI adds a 422 to every operation that takes a request body or a typed
    parameter, because that is what Pydantic would return on its own. This API
    installs a RequestValidationError handler that turns those into 400, so a
    422 can never actually come back. Leaving it in the docs would advertise a
    status code this API never returns, and the two schemas describing its
    shape would sit in Swagger's Schemas list describing nothing.
    """
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        tags=app.openapi_tags,
        routes=app.routes,
    )

    for operations in schema.get("paths", {}).values():
        for operation in operations.values():
            operation.get("responses", {}).pop("422", None)

    # Nothing references these once the 422s are gone.
    schemas = schema.get("components", {}).get("schemas", {})
    for name in ("HTTPValidationError", "ValidationError"):
        schemas.pop(name, None)

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
