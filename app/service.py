"""The rules, with no HTTP and no SQL in sight.

Everything this module knows about storage is the TaskRepository interface. It
never learns whether the tasks behind it are rows in Postgres or entries in a
list, which is what makes the swap in app/main.py a one-line change: there is
nothing in here to update.
"""

from typing import Optional

from app.errors import InvalidTask, TaskNotFound
from app.models import Stats, Task
from app.repositories.base import TaskRepository


class TaskService:
    """What the API is allowed to do, and what it refuses to do."""

    def __init__(self, repository: TaskRepository) -> None:
        # The repository arrives already built. This class never constructs one,
        # never imports a concrete implementation, and so never needs editing
        # when the storage changes.
        self._repository = repository

    # -- reads ---------------------------------------------------------------

    def list_tasks(
        self, done: Optional[bool] = None, search: Optional[str] = None
    ) -> list[Task]:
        """Every task, narrowed by the optional filters.

        An empty list is a valid answer — it means "nothing matched", which is
        a different thing from "that task does not exist"."""
        return self._repository.list_tasks(done=done, search=search)

    def get_task(self, task_id: int) -> Task:
        """One task, or TaskNotFound.

        Never answer "here you go" about something that is not there."""
        task = self._repository.get(task_id)
        if task is None:
            raise TaskNotFound(task_id)
        return task

    def stats(self) -> Stats:
        """Total, done and open counts.

        A client could count these itself from the task list, but doing it here
        is the point — an API can answer questions, not just hand over rows."""
        total, done = self._repository.counts()
        return Stats(total=total, done=done, open=total - done)

    # -- writes --------------------------------------------------------------

    def create_task(self, title: Optional[str]) -> Task:
        """Create a task from a title.

        The client supplies only the title. The id and the starting `done`
        value are the server's to decide — letting a client choose its own id
        is how you end up with collisions and overwritten data."""
        cleaned = (title or "").strip()
        if not cleaned:
            raise InvalidTask("Field 'title' is required and cannot be empty")
        return self._repository.add(cleaned)

    def update_task(
        self, task_id: int, title: Optional[str] = None, done: Optional[bool] = None
    ) -> Task:
        """Update a title, a done flag, or both.

        Order matters: check that the task exists *before* judging the body, so
        a request for task 99 is told the task is missing rather than being
        lectured about its fields."""
        if self._repository.get(task_id) is None:
            raise TaskNotFound(task_id)

        if title is None and done is None:
            raise InvalidTask("Provide at least one of 'title' or 'done'")

        cleaned: Optional[str] = None
        if title is not None:
            cleaned = title.strip()
            if not cleaned:
                raise InvalidTask("Field 'title' cannot be empty")

        task = self._repository.update(task_id, title=cleaned, done=done)
        if task is None:
            # Only reachable if the task was deleted between the check above and
            # the write — rare, but a real race once more than one client exists,
            # and 404 is still the honest answer.
            raise TaskNotFound(task_id)
        return task

    def delete_task(self, task_id: int) -> None:
        """Delete a task, or TaskNotFound if there was nothing to delete."""
        if not self._repository.delete(task_id):
            raise TaskNotFound(task_id)

    def reset(self) -> list[Task]:
        """Throw every task away and put the seed tasks back."""
        return self._repository.reset()
