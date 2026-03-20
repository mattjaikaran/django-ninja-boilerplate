# K3s Deployment

Lightweight Kubernetes deployment using plain manifests for [K3s](https://k3s.io/).

K3s is a certified Kubernetes distribution optimized for edge, IoT, and resource-constrained environments. It ships with Traefik as the default ingress controller and local-path as the default storage provisioner.

## Prerequisites

- K3s cluster (v1.25+)
- `kubectl` configured for your cluster
- Container registry with your Django image

## Quick Start

```bash
# 1. Create the namespace
kubectl apply -f deploy/k3s/namespace.yaml

# 2. Edit secrets (REQUIRED - change all CHANGE_ME values)
#    Generate a secret key: openssl rand -base64 50
#    Generate a DB password: openssl rand -base64 32
cp deploy/k3s/secrets.yaml deploy/k3s/secrets-local.yaml
# Edit secrets-local.yaml with real values
kubectl apply -f deploy/k3s/secrets-local.yaml

# 3. Apply config and infrastructure
kubectl apply -f deploy/k3s/configmap.yaml
kubectl apply -f deploy/k3s/postgres.yaml
kubectl apply -f deploy/k3s/redis.yaml

# 4. Wait for postgres and redis to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n django-ninja --timeout=120s
kubectl wait --for=condition=ready pod -l app=redis -n django-ninja --timeout=120s

# 5. Deploy the application
kubectl apply -f deploy/k3s/django.yaml

# 6. (Optional) Deploy Celery workers
kubectl apply -f deploy/k3s/celery.yaml

# 7. Configure ingress (edit host in ingress.yaml first)
kubectl apply -f deploy/k3s/ingress.yaml
```

## All-in-one Deploy

```bash
# Apply everything at once (edit secrets.yaml first!)
kubectl apply -f deploy/k3s/
```

## K3s vs K8s (Helm)

| Feature | K3s (this) | K8s (Helm) |
|---------|-----------|------------|
| Ingress controller | Traefik (built-in) | Nginx (requires install) |
| Storage | local-path (built-in) | Requires provisioner |
| Dependencies | None | Helm 3.x, Bitnami charts |
| Resource footprint | ~512MB RAM | ~2GB+ RAM |
| Config complexity | Plain YAML manifests | Helm values + templates |
| Best for | Single node, edge, dev | Multi-node production |

## Architecture

```
┌─────────────────────────────────────────┐
│  Traefik Ingress (built into k3s)       │
│  api.example.com → django:8000          │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│  Django (2 replicas)                     │
│  - Gunicorn (3 workers)                  │
│  - Runs migrations via init container    │
│  - Health: /api/health/                  │
└──────┬──────────────┬───────────────────┘
       │              │
┌──────▼──────┐ ┌─────▼─────┐
│  PostgreSQL │ │   Redis   │
│  (1 replica)│ │(1 replica)│
│  5Gi PVC    │ │ 1Gi PVC   │
└─────────────┘ └───────────┘

Optional:
┌─────────────────────┐ ┌──────────────┐
│  Celery Worker (1)  │ │ Celery Beat  │
│  concurrency: 2     │ │ (1 replica)  │
└─────────────────────┘ └──────────────┘
```

## Configuration

### Secrets (Required)

Edit `secrets.yaml` before deploying:

```bash
# Generate values
echo "SECRET_KEY: $(openssl rand -base64 50)"
echo "DB_PASSWORD: $(openssl rand -base64 32)"
echo "REDIS_PASSWORD: $(openssl rand -base64 32)"
```

### Custom Domain

Edit `ingress.yaml` and replace `api.example.com` with your domain.

### TLS/HTTPS

K3s includes Traefik which can auto-provision TLS certificates:

```bash
# Install cert-manager for automatic Let's Encrypt
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# Create a ClusterIssuer
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress: {}
EOF
```

Then add the annotation to `ingress.yaml`:
```yaml
annotations:
  cert-manager.io/cluster-issuer: "letsencrypt-prod"
```

### Scaling

```bash
# Scale Django replicas
kubectl scale deployment django -n django-ninja --replicas=3

# Scale Celery workers
kubectl scale deployment celery-worker -n django-ninja --replicas=2
```

### Resource Tuning

K3s nodes are typically smaller. Default resource limits are set conservatively:

| Component | CPU (req/limit) | Memory (req/limit) |
|-----------|----------------|---------------------|
| Django | 100m / 500m | 256Mi / 512Mi |
| PostgreSQL | 100m / 500m | 128Mi / 512Mi |
| Redis | 50m / 200m | 64Mi / 256Mi |
| Celery Worker | 100m / 500m | 256Mi / 512Mi |
| Celery Beat | 50m / 200m | 128Mi / 256Mi |

## Monitoring

```bash
# Check all pods
kubectl get pods -n django-ninja

# View Django logs
kubectl logs -l app=django -n django-ninja -f

# View Celery worker logs
kubectl logs -l component=worker -n django-ninja -f

# Check resource usage (requires metrics-server, included in k3s)
kubectl top pods -n django-ninja
```

## Troubleshooting

```bash
# Describe a failing pod
kubectl describe pod <pod-name> -n django-ninja

# Check events
kubectl get events -n django-ninja --sort-by='.lastTimestamp'

# Shell into Django pod
kubectl exec -it deployment/django -n django-ninja -- /bin/sh

# Run Django management commands
kubectl exec -it deployment/django -n django-ninja -- python manage.py shell

# Check Traefik ingress
kubectl get ingressroute -A
```

## Teardown

```bash
kubectl delete namespace django-ninja
```
