"""The storage the previous version used: a Python list in the server process.

Kept in the tree, unused, on purpose. It is the control in the experiment — the
thing the Postgres repository is measured against. Point app/main.py at this
class instead and every endpoint still works, exactly as before, right down to
losing every task when the process stops.
"""

from __future__ import annotations

from typing import Optional

from app.models import Task
from app.repositories.base import TaskRepository
from app.seed import SEED_TASKS


class InMemoryTaskRepository(TaskRepository):
    """Tasks in a list. Fast, dependency-free, and mortal."""

    def __init__(self) -> None:
        self._tasks: list[Task] = []
        self.reset()

    # -- queries -------------------------------------------------------------

    def list_tasks(
        self, done: Optional[bool] = None, search: Optional[str] = None
    ) -> list[Task]:
        results = self._tasks

        if done is not None:
            results = [task for task in results if task.done == done]

        if search is not None:
            needle = search.strip().lower()
            results = [task for task in results if needle in task.title.lower()]

        # A copy, so a caller iterating the result cannot be tripped up by a
        # later create or delete mutating the list underneath it.
        return list(results)

    def get(self, task_id: int) -> Optional[Task]:
        for task in self._tasks:
            if task.id == task_id:
                return task
        return None

    def counts(self) -> tuple[int, int]:
        return len(self._tasks), sum(1 for task in self._tasks if task.done)

    # -- commands ------------------------------------------------------------

    def add(self, title: str) -> Task:
        task = Task(id=self._next_id(), title=title, done=False)
        self._tasks.append(task)
        return task

    def update(
        self, task_id: int, title: Optional[str] = None, done: Optional[bool] = None
    ) -> Optional[Task]:
        task = self.get(task_id)
        if task is None:
            return None

        if title is not None:
            task.title = title
        if done is not None:
            task.done = done

        return task

    def delete(self, task_id: int) -> bool:
        task = self.get(task_id)
        if task is None:
            return False
        self._tasks.remove(task)
        return True

    def reset(self) -> list[Task]:
        # Rebuild from SEED_TASKS rather than keeping a shared copy around, so
        # editing a task at runtime cannot quietly rewrite the seed data that
        # reset is supposed to restore.
        self._tasks = [
            Task(id=index, title=title, done=done)
            for index, (title, done) in enumerate(SEED_TASKS, start=1)
        ]
        return list(self._tasks)

    # -- internals -----------------------------------------------------------

    def _next_id(self) -> int:
        """Pick the next free id.

        Deliberately max(existing) + 1 rather than len(tasks) + 1. After
        deleting a task the length drops, so len() + 1 would hand out an id that
        is already in use — two tasks with the same id, and the bug shows up
        much later. Postgres solves this with a sequence; here it is ours to
        get right."""
        return max((task.id for task in self._tasks), default=0) + 1
