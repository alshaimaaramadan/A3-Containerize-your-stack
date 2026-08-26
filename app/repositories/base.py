"""The interface between the service and whatever is actually storing tasks.

This is the seam the assignment is about. The service is written against this
class and nothing else: it never sees a list, a cursor, a connection or a row.
So "switch storage" means writing a new subclass and naming it in one line of
app/main.py — not touching the service, and not touching the routes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.models import Task


class TaskRepository(ABC):
    """Everything the service is allowed to ask of storage."""

    # -- lifecycle -----------------------------------------------------------
    # A connection pool has to be opened before use and closed on shutdown; a
    # Python list does not. Both answer these calls anyway, so the startup code
    # in app/main.py works with either implementation and does not have to ask
    # which one it got. Default to doing nothing; override where it matters.

    def open(self) -> None:
        """Get ready to serve requests. Called once, at application startup."""

    def close(self) -> None:
        """Release resources. Called once, at application shutdown."""

    # -- queries -------------------------------------------------------------

    @abstractmethod
    def list_tasks(
        self, done: Optional[bool] = None, search: Optional[str] = None
    ) -> list[Task]:
        """Return tasks in id order, narrowed by the optional filters.

        Filtering belongs here rather than in the service because only the
        repository knows the cheap way to do it: a WHERE clause for Postgres, a
        comprehension for the list. `search` matches a case-insensitive
        substring of the title; the two implementations must agree on that."""

    @abstractmethod
    def get(self, task_id: int) -> Optional[Task]:
        """Return one task, or None if no task has that id."""

    @abstractmethod
    def counts(self) -> tuple[int, int]:
        """Return (total, done). The service works out `open` from those."""

    # -- commands ------------------------------------------------------------

    @abstractmethod
    def add(self, title: str) -> Task:
        """Store a new task with this title and return it, id assigned.

        The id is the storage layer's to hand out, and the new task starts
        `done: false`."""

    @abstractmethod
    def update(
        self, task_id: int, title: Optional[str] = None, done: Optional[bool] = None
    ) -> Optional[Task]:
        """Apply whichever fields were given and return the task, or None if no
        task has that id. Passing neither field leaves the task untouched."""

    @abstractmethod
    def delete(self, task_id: int) -> bool:
        """Delete the task. True if it existed, False if there was nothing to delete."""

    @abstractmethod
    def reset(self) -> list[Task]:
        """Throw everything away and put the seed tasks back. Returns them."""
