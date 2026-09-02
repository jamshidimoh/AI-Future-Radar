FROM python:3.11-slim

ARG VERSION=dev
LABEL org.opencontainers.image.title="AI Future Radar"
LABEL org.opencontainers.image.description="AI-first future technology intelligence and publication pipeline"
LABEL org.opencontainers.image.source="https://github.com/jamshidimoh/AI-Future-Radar"
LABEL org.opencontainers.image.version="${VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system radar && useradd --system --gid radar --create-home radar

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . ./

RUN chown -R radar:radar /app
USER radar

CMD ["python", "-u", "scripts/production_with_ranking_audit.py"]
