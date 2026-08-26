"""How a route gets hold of the service.

The service instance is built once, at startup, in app/main.py and parked on
`app.state`. Routes ask for it through this function rather than importing it,
which keeps app/routes.py free of any knowledge of how the application was
wired together — and free of any knowledge of which repository it got.
"""

from fastapi import Request

from app.service import TaskService


def get_service(request: Request) -> TaskService:
    """Return the application's TaskService."""
    return request.app.state.service
