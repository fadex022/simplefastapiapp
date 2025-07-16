# SimpleFastApiApp

A simple FastAPI application with OpenTelemetry integration, containerized with Docker and deployed to Kubernetes.

## Features

- FastAPI web framework
- SQLAlchemy ORM with PostgreSQL
- Redis caching
- OpenTelemetry instrumentation
- Docker containerization
- Kubernetes deployment
- CI/CD with Jenkins

## Development

This project uses Poetry for dependency management.

### Setup

```bash
# Install dependencies
poetry install

# Run the application
uvicorn main:app --reload
```

### Testing

```bash
# Run tests
poetry run pytest
```

## Deployment

The application is deployed to Kubernetes using the configuration in the `kubernetes/` directory.

## License

This project is licensed under the MIT License.