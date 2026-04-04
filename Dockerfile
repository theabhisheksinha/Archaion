FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire Archaion app source
COPY app/ ./app/

# Expose port 9999 for the unified FastAPI+Frontend server
EXPOSE 9999

# Start Uvicorn
CMD ["uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "9999"]
