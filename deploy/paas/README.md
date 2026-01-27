# PaaS Deployment Configurations

This directory contains deployment configurations for various Platform-as-a-Service providers.

## Railway

### Quick Deploy

1. Connect your repository to Railway
2. Railway will auto-detect `railway.json` or `railway.toml`
3. Add required environment variables in the dashboard

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Django secret key |
| `ALLOWED_HOSTS` | Yes | Comma-separated hostnames |
| `DATABASE_URL` | Auto | Provided by Railway PostgreSQL |
| `REDIS_URL` | Auto | Provided by Railway Redis |

### Deploy Command

```bash
# Using Railway CLI
railway up
```

## Render

### Quick Deploy

1. Create a new Blueprint in Render dashboard
2. Connect your repository
3. Render will auto-detect `render.yaml`

### Blueprint Deployment

```bash
# Using Render CLI
render blueprint apply
```

### Services Created

- **django-api**: Main web service
- **postgres**: PostgreSQL database
- **redis**: Redis cache

## Fly.io

For Fly.io deployment, use the Docker configuration:

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Launch app
fly launch --dockerfile deploy/docker/Dockerfile.single

# Set secrets
fly secrets set SECRET_KEY="your-secret-key"
fly secrets set DATABASE_URL="postgres://..."
fly secrets set REDIS_URL="redis://..."

# Deploy
fly deploy
```

## Environment Variables

All PaaS deployments require these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | Generated |
| `DEBUG` | Debug mode (set to 0) | `0` |
| `ALLOWED_HOSTS` | Allowed hostnames | `.railway.app,.onrender.com` |
| `DATABASE_URL` | PostgreSQL connection string | `postgres://...` |
| `REDIS_URL` | Redis connection string | `redis://...` |
| `DJANGO_SETTINGS_MODULE` | Settings module | `api.settings` |

## Health Check

All configurations use `/api/health/` as the health check endpoint.
