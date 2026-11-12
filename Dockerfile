FROM python:3.13-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

# Dependencies first, so changing your code doesn't reinstall them
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --locked --no-dev --no-install-project

# Then the app
COPY src ./src
COPY public ./public
COPY migrations ./migrations
RUN uv sync --locked --no-dev

# Don't run as root. The same user ID as yours means files in data/ stay yours.
RUN useradd --uid 1000 --create-home app && mkdir -p data && chown app data
USER app

# Without this, each worker thread keeps its own pool of freed memory, which adds up on a 1 GB server.
ENV MALLOC_ARENA_MAX=2

EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "enclothed.api:app", "--host", "0.0.0.0", "--port", "8000"]
