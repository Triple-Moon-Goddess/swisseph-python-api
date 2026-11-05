# Pinned to one image (python:3.11-slim, multi-arch index, read 2026-11-05) so a build
# cannot pick up an unreviewed base; bump the digest on purpose. OS packages are still
# patched below at every build.
FROM python:3.11-slim@sha256:65bd3d9f1d7fa268dd1909973ba7eb4bdf41f6dcf2cfbe76ba9528b170f3fd79

# Patch OS packages in the base image (R22: acl, perl, attr and zlib advisories)
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
# setuptools and wheel are build tools the server never imports; removing them drops their
# vulnerable vendored packages (wheel, jaraco.context) from the image (R22)
RUN pip install --no-cache-dir -r requirements.txt && pip uninstall -y setuptools wheel

# Copy ephemeris data
COPY ephe/ /app/ephe/

# Copy server code and download script
COPY server.py .
COPY download_asteroids.py .

# Run as an unprivileged user, not root. It owns only the ephemeris folder, which
# download_asteroids.py fills at startup; the code and libraries stay root-owned.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app && chown -R app:app /app/ephe
USER 10001

# Expose port (Cloud Run will set PORT env var, default to 8000 for local dev)
EXPOSE 8000

# Download asteroid files on startup, then run server
# Use PORT env var (Cloud Run standard) or default to 8000
CMD python3 download_asteroids.py && uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
