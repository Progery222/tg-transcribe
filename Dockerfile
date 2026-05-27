FROM python:3.12-slim AS builder

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
COPY src/ src/

RUN uv sync --frozen --no-dev


FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -r -u 1001 botuser \
 && mkdir -p /app/data \
 && chown -R botuser:botuser /app

COPY --from=builder --chown=botuser:botuser /app /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1

USER botuser

CMD ["python", "-m", "bot"]
