FROM cr.fluentbit.io/fluent/fluent-bit:5.1.5@sha256:2740f387f6e68fab66d28e4fa6a853387b9cab6ffb4cb78958f69bba4eb0e7b4 AS collector
FROM ghcr.io/astral-sh/uv:0.9.5 AS uv
FROM python:3.11-slim-trixie
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tini libssl3t64 libsasl2-2 libsystemd0 libzstd1 libyaml-0-2 libcurl4t64 libpq5 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=collector /fluent-bit /fluent-bit
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable
COPY container /app/container
COPY tests /app/tests
RUN /fluent-bit/bin/fluent-bit --version && \
    useradd --uid 10001 --create-home app && \
    mkdir -p /logs /tmp/runtime && \
    chown -R app:app /logs /tmp/runtime
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 \
    PORT=8080 LOG_PROJECT=calendarhelperai LOG_ENV=dev LOG_OUTPUT=file LOGGING_ENABLED=true \
    APP_LOG_FILE=/logs/spool/events.jsonl
USER app
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD python /app/container/healthcheck.py
ENTRYPOINT ["/usr/bin/tini", "--", "python", "/app/container/runtime.py"]
