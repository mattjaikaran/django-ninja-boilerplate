# Kubernetes Deployment

This directory contains Kubernetes deployment configurations using Helm.

## Prerequisites

- Kubernetes cluster (1.25+)
- Helm 3.x
- kubectl configured for your cluster

## Quick Start

```bash
# Add Bitnami repo for dependencies
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Install the chart
helm install my-app ./deploy/kubernetes/helm/django-ninja-stack \
  --set postgresql.auth.password=your-db-password \
  --set image.repository=your-registry/django-ninja-stack \
  --set image.tag=latest
```

## Configuration

### Required Secrets

Before deploying, create a secret with your Django secret key:

```bash
kubectl create secret generic django-secrets \
  --from-literal=SECRET_KEY=$(openssl rand -base64 50)
```

### Custom Values

Create a `values-production.yaml` file:

```yaml
image:
  repository: your-registry/django-ninja-stack
  tag: "1.0.0"

backend:
  replicaCount: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10

ingress:
  enabled: true
  hosts:
    - host: api.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: api-tls
      hosts:
        - api.yourdomain.com

postgresql:
  auth:
    password: "secure-password"
```

Deploy with custom values:

```bash
helm install my-app ./deploy/kubernetes/helm/django-ninja-stack \
  -f values-production.yaml
```

## Components

### Backend Deployment

- Runs Django with Gunicorn
- Health checks on `/api/health/`
- Horizontal Pod Autoscaler (optional)

### Celery Worker (optional)

Enable with:

```yaml
celeryWorker:
  enabled: true
  replicaCount: 2
```

### Celery Beat (optional)

Enable with:

```yaml
celeryBeat:
  enabled: true
```

### PostgreSQL

Uses Bitnami PostgreSQL subchart. For external database:

```yaml
postgresql:
  enabled: false

externalDatabase:
  host: your-db-host.com
  port: 5432
  user: django
  password: secret
  database: django_db
```

### Redis

Uses Bitnami Redis subchart. For external Redis:

```yaml
redis:
  enabled: false

externalRedis:
  host: your-redis-host.com
  port: 6379
  password: ""
```

## Upgrade

```bash
helm upgrade my-app ./deploy/kubernetes/helm/django-ninja-stack \
  -f values-production.yaml
```

## Uninstall

```bash
helm uninstall my-app
```

## Troubleshooting

### Check pod status

```bash
kubectl get pods -l app.kubernetes.io/name=django-ninja-stack
```

### View logs

```bash
kubectl logs -l app.kubernetes.io/component=backend -f
```

### Check migrations job

```bash
kubectl get jobs
kubectl logs job/my-app-django-ninja-stack-migrations
```
