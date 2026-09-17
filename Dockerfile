FROM python:3.11-slim

# Prevent Python from writing bytecode and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies: tesseract-ocr is required by pytesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Strict verification: confirm tesseract is present and executable on PATH
RUN which tesseract && tesseract --version

# Copy requirements and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Create persistent storage directory for SQLite database
RUN mkdir -p /data
ENV PACKSIGHT_DB_DIR=/data

# Copy ONLY the root-level PackSight application files
# (Explicitly omitting ./backend, ./frontend, ./sih26034-legal-metrology, and docker-compose.yml)
COPY main.py scanner.py ocr_rules.py database.py models.py schemas.py auth_utils.py report_generator.py index.html packsight-logo-transparent.png ./

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
