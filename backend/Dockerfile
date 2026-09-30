FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
RUN pip wheel --wheel-dir /wheels .

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install /wheels/* \
    && rm -rf /wheels \
    && useradd --create-home --uid 10001 appuser

COPY alembic.ini ./
COPY migrations ./migrations
COPY render-start.sh ./
RUN chmod +x /app/render-start.sh \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

CMD ["/app/render-start.sh"]
