"""Storage implementations. Pick one in the composition root (app/main.py)."""

from app.repositories.base import TaskRepository
from app.repositories.memory import InMemoryTaskRepository
from app.repositories.postgres import PostgresTaskRepository

__all__ = ["TaskRepository", "InMemoryTaskRepository", "PostgresTaskRepository"]
