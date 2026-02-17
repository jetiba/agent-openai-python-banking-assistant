# Use official Python slim image
FROM --platform=linux/amd64 python:3.11-slim-bookworm

# Set work directory
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files first (for layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-dev

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Start the app
CMD [".venv/bin/python", "main.py"]

