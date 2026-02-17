FROM python:3.10-slim

WORKDIR /app

# Copy source code
COPY . /app/harvester

# Set python path
ENV PYTHONPATH=/app

# Default command
CMD ["python", "-m", "harvester.main", "--loop"]
