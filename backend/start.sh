#!/bin/sh
set -e

# Default to port 8000 if PORT not set
PORT=${PORT:-8000}

# Log the port we are starting on
echo "Starting application on port $PORT"

# Start Uvicorn
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
