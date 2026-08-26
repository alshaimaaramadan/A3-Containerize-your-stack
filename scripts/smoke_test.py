"""Exercise every endpoint against the in-memory repository.

Proves routes + service + wiring work without needing Docker. The SQL path is
verified separately, against the real database.
"""
import os
import sys

os.environ.setdefault("DATABASE_URL", "postgresql://unused:unused@localhost:5432/unused")

from fastapi.testclient import TestClient  # noqa: E402

import app.main as main  # noqa: E402
from app.repositories.memory import InMemoryTaskRepository  # noqa: E402

# Swap in the list-backed repository, exactly the way app/main.py documents.
main.repository = InMemoryTaskRepository()

failures = []


def check(label, actual, expected):
    if actual != expected:
        failures.append(f"{label}: expected {expected!r}, got {actual!r}")
        print(f"  FAIL {label}: expected {expected!r}, got {actual!r}")
    else:
        print(f"  ok   {label}")


with TestClient(main.app) as client:
    r = client.get("/")
    check("GET / status", r.status_code, 200)
    check("GET / name", r.json()["name"], "Task API")

    check("GET /health", client.get("/health").json(), {"status": "ok"})

    r = client.get("/tasks")
    check("GET /tasks status", r.status_code, 200)
    check("GET /tasks seed count", len(r.json()), 3)
    check("GET /tasks first", r.json()[0], {"id": 1, "title": "Read the assignment", "done": True})

    check("filter done=true", [t["id"] for t in client.get("/tasks?done=true").json()], [1])
    check("filter done=false", [t["id"] for t in client.get("/tasks?done=false").json()], [2, 3])
    check("search 'api'", [t["id"] for t in client.get("/tasks?search=api").json()], [2])
    check("search+done", [t["id"] for t in client.get("/tasks?search=the&done=false").json()], [2, 3])
    check("search no match", client.get("/tasks?search=zzz").json(), [])

    check("GET /tasks/1", client.get("/tasks/1").json()["title"], "Read the assignment")
    r = client.get("/tasks/99")
    check("GET /tasks/99 status", r.status_code, 404)
    check("GET /tasks/99 body", r.json(), {"error": "Task 99 not found"})

    r = client.post("/tasks", json={"title": "  Buy milk  "})
    check("POST /tasks status", r.status_code, 201)
    check("POST /tasks body", r.json(), {"id": 4, "title": "Buy milk", "done": False})

    check("POST empty body", client.post("/tasks", json={}).status_code, 400)
    check("POST empty body msg", client.post("/tasks", json={}).json(),
          {"error": "Field 'title' is required and cannot be empty"})
    check("POST blank title", client.post("/tasks", json={"title": "   "}).status_code, 400)
    r = client.post("/tasks", json={"title": ["nope"]})
    check("POST wrong type status", r.status_code, 400)
    check("POST wrong type body", r.json(), {"error": "Invalid request body"})
    r = client.post("/tasks", content=b"{not json", headers={"content-type": "application/json"})
    check("POST bad json", r.status_code, 400)

    r = client.put("/tasks/4", json={"done": True})
    check("PUT done", r.json(), {"id": 4, "title": "Buy milk", "done": True})
    r = client.put("/tasks/4", json={"title": "Buy oat milk", "done": False})
    check("PUT both", r.json(), {"id": 4, "title": "Buy oat milk", "done": False})
    check("PUT unknown id", client.put("/tasks/99", json={"done": True}).status_code, 404)
    r = client.put("/tasks/1", json={})
    check("PUT empty status", r.status_code, 400)
    check("PUT empty msg", r.json(), {"error": "Provide at least one of 'title' or 'done'"})
    check("PUT blank title", client.put("/tasks/1", json={"title": "  "}).json(),
          {"error": "Field 'title' cannot be empty"})
    # 404 must win over 400: unknown id with an empty body is still a 404.
    check("PUT 404 beats 400", client.put("/tasks/99", json={}).status_code, 404)

    check("GET /stats", client.get("/stats").json(), {"total": 4, "done": 1, "open": 3})

    r = client.delete("/tasks/4")
    check("DELETE status", r.status_code, 204)
    check("DELETE body empty", r.content, b"")
    check("DELETE twice", client.delete("/tasks/4").status_code, 404)

    # id reuse: after deleting 4, the next task must not be handed id 4 again
    # while max(id) is 3 -- it should be 4 here, but never a duplicate of a live id.
    check("ids after delete", [t["id"] for t in client.get("/tasks").json()], [1, 2, 3])

    r = client.post("/reset")
    check("POST /reset status", r.status_code, 200)
    check("POST /reset ids", [t["id"] for t in r.json()["tasks"]], [1, 2, 3])
    check("after reset", len(client.get("/tasks").json()), 3)

    r = client.get("/no-such-path")
    check("unknown path status", r.status_code, 404)
    check("unknown path shape", list(r.json().keys()), ["error"])

    r = client.request("POST", "/tasks/1")
    check("wrong method shape", list(r.json().keys()), ["error"])

    schema = client.get("/openapi.json").json()
    has_422 = any("422" in op.get("responses", {})
                  for path in schema["paths"].values() for op in path.values())
    check("no 422 in docs", has_422, False)
    check("no stray schemas", "HTTPValidationError" in schema.get("components", {}).get("schemas", {}), False)

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    sys.exit(1)
print("all checks passed")
