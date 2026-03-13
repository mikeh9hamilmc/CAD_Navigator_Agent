# CAD Navigator Agent — Backend
# Python 3.12 slim image running FastAPI/uvicorn WebSocket server
#
# GEMINI_API_KEY is NOT a build argument.
# It is injected at runtime as a Cloud Run environment variable sourced
# from Google Secret Manager (see CLOUD_RUN.md).

FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (leverages Docker layer cache)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source files
COPY backend/ ./

# Cloud Run requires containers to listen on port 8080 (or $PORT)
EXPOSE 8080

# Run via python server.py so the __main__ block executes with
# ws_ping_interval=None — the Python API correctly disables pings.
# The CLI equivalent (--ws-ping-interval 0) means "ping every 0 seconds",
# which causes immediate 1011 keepalive timeouts. Always use this form.
CMD ["python", "server.py"]
