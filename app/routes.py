"""The HTTP layer: paths, status codes, and what the docs say.

These handlers do no work. They read the request, hand it to the service, and
turn the answer into a response. That is why swapping Postgres in changed
nothing here — there was nothing here to change.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Response

from app.dependencies import get_service
from app.models import Stats, Task, TaskCreate, TaskUpdate
from app.service import TaskService

# Reusable Swagger documentation for the two error shapes this API returns.
NOT_FOUND = {
    "description": "No task has that id",
    "content": {"application/json": {"example": {"error": "Task 99 not found"}}},
}
BAD_REQUEST = {
    "description": "The request body was missing or malformed",
    "content": {
        "application/json": {
            "example": {"error": "Field 'title' is required and cannot be empty"}
        }
    },
}

router = APIRouter()


# --------------------------------------------------------------------------
# Information endpoints
# --------------------------------------------------------------------------


@router.get("/", summary="API information", tags=["meta"])
def root():
    """Describe this API: its name, its version, and where to go next."""
    # Deliberately says nothing about storage. A route that named the database
    # would be a route that had to be edited when the database changed, which is
    # the exact coupling this layout exists to avoid.
    return {
        "name": "Task API",
        "version": "2.0",
        "endpoints": ["/tasks"],
    }


@router.get("/health", summary="Health check", tags=["meta"])
def health():
    """Return 200 with a fixed body so uptime checks have something to poll.

    Deliberately a liveness check and nothing more: it answers "is this process
    up", not "is the database reachable". The container HEALTHCHECK in the
    Dockerfile polls this."""
    return {"status": "ok"}


# --------------------------------------------------------------------------
# Read endpoints
# --------------------------------------------------------------------------


@router.get(
    "/tasks",
    response_model=list[Task],
    summary="List every task",
    tags=["tasks"],
)
def list_tasks(
    done: Optional[bool] = Query(
        default=None,
        description="Keep only finished (true) or unfinished (false) tasks.",
    ),
    search: Optional[str] = Query(
        default=None,
        description="Keep only tasks whose title contains this text (case-insensitive).",
    ),
    service: TaskService = Depends(get_service),
):
    """Return every task, narrowed by the optional filters.

    Both filters are query parameters, and they compose: `?done=false&search=milk`
    means "unfinished tasks about milk". With neither, you get everything."""
    return service.list_tasks(done=done, search=search)


@router.get(
    "/tasks/{task_id}",
    response_model=Task,
    responses={404: NOT_FOUND},
    summary="Get one task by id",
    tags=["tasks"],
)
def get_task(task_id: int, service: TaskService = Depends(get_service)):
    """Return a single task, or 404 if no task has that id."""
    return service.get_task(task_id)


# --------------------------------------------------------------------------
# Create
# --------------------------------------------------------------------------


@router.post(
    "/tasks",
    status_code=201,
    response_model=Task,
    responses={400: BAD_REQUEST},
    summary="Create a task",
    tags=["tasks"],
)
def create_task(payload: TaskCreate, service: TaskService = Depends(get_service)):
    """Create a task from a title and return it with 201 Created."""
    return service.create_task(payload.title)


# --------------------------------------------------------------------------
# Update and delete
# --------------------------------------------------------------------------


@router.put(
    "/tasks/{task_id}",
    response_model=Task,
    responses={400: BAD_REQUEST, 404: NOT_FOUND},
    summary="Update a task",
    tags=["tasks"],
)
def update_task(
    task_id: int, payload: TaskUpdate, service: TaskService = Depends(get_service)
):
    """Update a task's title, its done flag, or both, and return the result."""
    return service.update_task(task_id, title=payload.title, done=payload.done)


@router.delete(
    "/tasks/{task_id}",
    status_code=204,
    response_class=Response,
    responses={204: {"description": "Deleted. No content."}, 404: NOT_FOUND},
    summary="Delete a task",
    tags=["tasks"],
)
def delete_task(task_id: int, service: TaskService = Depends(get_service)):
    """Delete a task and return 204 No Content — success, nothing to say.

    204 means the body must be genuinely empty, so we hand back a bare Response
    rather than returning None and letting FastAPI serialise `null` into a body
    the status code promised would not be there."""
    service.delete_task(task_id)
    return Response(status_code=204)


# --------------------------------------------------------------------------
# Extras
# --------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=Stats,
    summary="Count tasks by status",
    tags=["meta"],
)
def stats(service: TaskService = Depends(get_service)):
    """Summarise the list: how many tasks in total, how many done, how many open."""
    return service.stats()


@router.post("/reset", summary="Restore the seed tasks", tags=["meta"])
def reset(service: TaskService = Depends(get_service)):
    """Throw away every task and put the three seed tasks back.

    Worth knowing now that storage is real and durable: this permanently
    destroys stored data. It is a demo convenience, and it would not survive
    contact with production."""
    tasks = service.reset()
    return {"message": "Tasks reset to the original 3 seed tasks", "tasks": tasks}
