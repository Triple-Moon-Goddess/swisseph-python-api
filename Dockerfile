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

# Expose port
EXPOSE 8000

# Download asteroid files on startup, then run server
CMD python3 download_asteroids.py && uvicorn server:app --host 0.0.0.0 --port 8000
