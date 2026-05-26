FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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
