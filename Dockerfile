FROM python:3.12-slim

# Add a non-root user, improve security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY requirements.txt .

# Install curl and Python dependencies in one RUN step, cleaning apt cache to save space
RUN apt-get update && apt-get install -y curl && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /var/lib/apt/lists/*

COPY src/ ./src/

# Adding non-root user
RUN chown -R appuser:appuser /app
USER appuser

CMD ["python", "src/data_generator.py"]
