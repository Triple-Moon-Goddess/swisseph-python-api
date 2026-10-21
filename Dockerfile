FROM python:3.11-slim

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

# Expose port (Cloud Run will set PORT env var, default to 8000 for local dev)
EXPOSE 8000

# Download asteroid files on startup, then run server
# Use PORT env var (Cloud Run standard) or default to 8000
CMD python3 download_asteroids.py && uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
