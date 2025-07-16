FROM python:3.13

# Set the working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false

# Create a non-root user
RUN addgroup --system --gid 1001 fadel \
    && adduser --system --uid 1001 --ingroup fadel fadel \
    && apt-get update \
    && apt-get install -y --no-install-recommends build-essential bash curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN python -m pip install --upgrade pip \
    && pip install poetry

# Copy only pyproject.toml and poetry.lock (if exists) to leverage Docker cache
COPY --chown=fadel:fadel pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY --chown=fadel:fadel . .

RUN chown -R fadel:fadel /app

# Switch to non-root user
USER fadel

# Expose port
EXPOSE 8000

# Default command uses bash for compatibility with Vault secret handling
ENTRYPOINT ["/bin/bash", "-c"]
CMD ["exec uvicorn main:app --host 0.0.0.0 --port 8000"]