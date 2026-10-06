# Copyright (c) 2026 8ecker.de
FROM python:3.12.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    HOME=/home/scraper

WORKDIR /opt/solaredge
COPY requirements.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu ca-certificates tzdata \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium \
    && useradd --create-home --uid 1000 --shell /usr/sbin/nologin scraper \
    && chmod -R a+rX /opt/playwright \
    && rm -rf /var/lib/apt/lists/* /root/.cache

# Keep version labels below dependencies so updates can reuse Chromium layers.
ARG BUILD_VERSION=0.3.11
ARG BUILD_ARCH=amd64
LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.authors="8ecker.de" \
      org.opencontainers.image.vendor="8ecker.de" \
      org.opencontainers.image.description="SolarEdge Web Scraper. Copyright (c) 2026 8ecker.de"

COPY app ./app
COPY tools ./tools
COPY run.sh /run.sh
RUN chmod 0755 /run.sh

# Supervisor supplies persistent /data and its options.json. run.sh prepares
# only the application's private files, then drops privileges before Chromium.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python", "-m", "app.health", "--check"]
ENTRYPOINT ["/run.sh"]
CMD ["python", "-m", "app.main"]
