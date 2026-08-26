"""What can go wrong, expressed without mentioning HTTP.

The service raises these. `app/main.py` is the only place that knows a
TaskNotFound is a 404 — which is why the service can be tested, or reused
behind a CLI or a queue worker, without importing a web framework.
"""


class TaskError(Exception):
    """Base class, so one `except` can catch anything this domain raises."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class TaskNotFound(TaskError):
    """No task has that id. Rendered as 404."""

    def __init__(self, task_id: int):
        super().__init__(f"Task {task_id} not found")
        self.task_id = task_id


class InvalidTask(TaskError):
    """The client asked for something the rules forbid. Rendered as 400."""
