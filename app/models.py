"""The shapes that cross the wire.

Unchanged from the in-memory version: the same request bodies, the same
response body. Swapping the storage did not change what a client sends or
receives, which is the whole point of the exercise.
"""

from typing import Optional

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    """What a client sends to create a task: a title, and nothing else."""

    title: Optional[str] = Field(default=None, examples=["Buy milk"])


class TaskUpdate(BaseModel):
    """An update may carry a new title, a new `done` value, or both. Sending
    neither is a mistake worth reporting rather than a no-op to shrug at."""

    title: Optional[str] = Field(default=None, examples=["Buy oat milk"])
    done: Optional[bool] = Field(default=None, examples=[True])


class Task(BaseModel):
    """What the API sends back, and what a repository hands to the service.

    `title` is declared Optional on TaskCreate on purpose. If Pydantic enforced
    it, a missing title would come back as HTTP 422; this API is specified to
    answer 400, so the field is optional to Pydantic and checked by the service,
    where we control the status code and the message."""

    id: int = Field(examples=[1])
    title: str = Field(examples=["Buy milk"])
    done: bool = Field(examples=[False])


class Stats(BaseModel):
    """Counts for GET /stats."""

    total: int = Field(examples=[3])
    done: int = Field(examples=[1])
    open: int = Field(examples=[2])
