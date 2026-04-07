# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Final Image
FROM python:3.11-slim

WORKDIR /app
# Copy installed dependencies
COPY --from=builder /root/.local /root/.local

# Ensure the local bin is on PATH
ENV PATH=/root/.local/bin:$PATH

# Copy the application source code
COPY app/ ./app/

EXPOSE 9999

# Start the unified FastAPI + Frontend server
CMD ["python", "-m", "uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "9999"]
