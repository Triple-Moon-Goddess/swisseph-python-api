# Pinned to one image (python:3.11-slim, multi-arch index, read 2026-11-16) so a rebuild cannot
# pick up an unreviewed base (SOP 56 §2). Bump the digest on purpose; OS packages are still
# patched below at every build.
FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

# Patch OS packages in the base image (R22: acl, perl, attr and zlib advisories)
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
# setuptools and wheel are build tools the server never imports; removing them drops their
# vulnerable vendored packages (wheel, jaraco.context) from the image (R22). pip is only
# needed for this install: nothing at runtime calls it, so it is removed too, with the copy
# ensurepip keeps, which drops its scanner findings (TRI-14). test_no_pip_in_image.py checks.
RUN pip install --no-cache-dir -r requirements.txt \
 && pip uninstall -y setuptools wheel \
 && python -m pip uninstall -y pip \
 && rm -rf /usr/local/lib/python3.11/ensurepip/_bundled

# Copy ephemeris data
COPY ephe/ /app/ephe/

# Copy server code and download script
COPY server.py .
COPY download_asteroids.py .

# Run as an unprivileged user, not root (SOP 56 §2). It owns only the ephemeris folder, which
# download_asteroids.py may refill at startup; the code and libraries stay root-owned.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app && chown -R app:app /app/ephe
USER 10001

# Expose port (Cloud Run will set PORT env var, default to 8000 for local dev)
EXPOSE 8000

# Download asteroid files on startup, then run server
# Use PORT env var (Cloud Run standard) or default to 8000
CMD python3 download_asteroids.py && uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
