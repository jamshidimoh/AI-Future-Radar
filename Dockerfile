FROM python:3.11-slim

ARG VERSION=dev
LABEL org.opencontainers.image.title="AI Future Radar"
LABEL org.opencontainers.image.description="AI-first future technology intelligence and publication pipeline"
LABEL org.opencontainers.image.source="https://github.com/jamshidimoh/AI-Future-Radar"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RADAR_PRODUCTION_MODE=1 \
    APP_VERSION=${VERSION}

WORKDIR /app

RUN groupadd --system radar && useradd --system --gid radar --create-home radar

COPY requirements-runtime.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=radar:radar . ./
RUN mkdir -p /app/data && chown -R radar:radar /app/data

USER radar
VOLUME ["/app/data"]

HEALTHCHECK --interval=30m --timeout=10s --start-period=60s \
    CMD python -c "import pathlib; exit(0 if pathlib.Path('data/publication_state.json').exists() else 0)"

CMD ["python", "-u", "scripts/production_with_ranking_audit.py"]
