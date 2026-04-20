# ── Build Stage ───────────────────────────────────────────────
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all remaining application files
COPY . .

# Set environment variable for Cloud Run
ENV PORT=8080

# Expose the port
EXPOSE 8080

# Create non-root user for security
RUN useradd --create-home appuser
USER appuser

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
