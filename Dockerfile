# Local development image, shared by the `api` and `worker` services — same code,
# different entrypoint. Source is bind-mounted by Compose, so this image only owns
# the interpreter and the dependencies.
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# The virtualenv lives outside /app so the Compose bind mount cannot shadow it.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked

# Dev dependencies are included on purpose: this image also runs pytest and ruff.
# A production image should build with `uv sync --locked --no-dev`.

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
