FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
# Optional build-only CA bundle for networks with a trusted TLS inspection proxy.
# The bundle is never copied into the final image; ordinary builds use system trust.
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    pip install --no-cache-dir --disable-pip-version-check -r requirements.txt
COPY app ./app

ARG BUILD_VERSION=0.1.7
ARG BUILD_ARCH=amd64
LABEL io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}" \
    org.opencontainers.image.title="Maverick Timelapse" \
    org.opencontainers.image.source="https://github.com/ambient-home-systems/Maverick_timelapse" \
    org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1
EXPOSE 8099
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8099", "--no-proxy-headers"]
