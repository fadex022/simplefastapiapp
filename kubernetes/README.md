# Kubernetes Configuration

This directory contains Kubernetes configuration files for deploying the SimpleFastApiApp.

## Files

- `deployment.yaml`: Defines the deployment configuration for the application
- `service.yaml`: Defines the service to expose the application
- `db-secret.yaml`: Contains database connection credentials
- `redis-secret.yaml`: Contains Redis connection credentials

## Secrets

Before deploying the application, you need to update the Secret files with your actual production values:

### Database Secret

Update `db-secret.yaml` with your actual database credentials:

```yaml
stringData:
  host: "your-db-host"  # Database hostname or IP
  dbname: "your-db-name"  # Database name
  username: "your-db-user"  # Database username
  password: "your-db-password"  # Database password
  port: "5432"  # Database port (usually 5432 for PostgreSQL)
```

### Redis Secret

Update `redis-secret.yaml` with your actual Redis credentials:

```yaml
stringData:
  host: "your-redis-host"  # Redis hostname or IP
  port: "6379"  # Redis port (usually 6379)
  password: "your-redis-password"  # Redis password
```

## Deployment

To deploy the application and its resources:

1. First, create the Secrets:

```bash
kubectl apply -f kubernetes/db-secret.yaml
kubectl apply -f kubernetes/redis-secret.yaml
```

2. Then deploy the application:

```bash
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml
```

## Security Note

The Secret files in this repository contain placeholder values. Never commit actual production credentials to your repository. Consider using a secrets management solution like HashiCorp Vault, AWS Secrets Manager, or Kubernetes external secrets for production environments.