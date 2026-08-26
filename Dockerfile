# The API, as an image. The database does not need one — it uses the official
# postgres image, configured in docker-compose.yml.

FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE: .pyc files are dead weight in an image layer.
# PYTHONUNBUFFERED: without it, print and log output sits in a buffer and
# `docker compose logs` shows nothing until the process exits — which is
# exactly when you most want to see it.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# Dependencies before source, in their own layer. Docker caches by step, so
# editing app/main.py rebuilds only the last two lines instead of reinstalling
# FastAPI every time.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Run as a normal user. A container that never needs to write to its own
# filesystem has no reason to be root inside it, and a compromised process
# with uid 0 is a worse day than one without.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /code
USER appuser

EXPOSE 8000

# Docker's own liveness check, so `docker compose ps` reports whether the API
# is answering rather than merely running. urllib is in the standard library —
# no curl, and nothing extra installed just to ask a question.
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

# No --reload here. Reload is a development convenience that watches the
# filesystem; in a container the source does not change under the process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
