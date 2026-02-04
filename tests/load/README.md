# Load Testing with Locust

This directory contains load testing scenarios for the Django Ninja API using [Locust](https://locust.io/).

## Prerequisites

Install Locust and testing dependencies:

```bash
# Using uv
uv pip install -e ".[testing]"

# Or directly
pip install locust
```

## Quick Start

### Start the Web UI

```bash
# From project root
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

Then open http://localhost:8089 in your browser.

### Run Headless (CLI)

```bash
# Quick test: 10 users, 2 spawn rate, 30 seconds
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --headless \
    -u 10 \
    -r 2 \
    -t 30s

# Moderate load: 50 users, 5 spawn rate, 2 minutes
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --headless \
    -u 50 \
    -r 5 \
    -t 2m

# Heavy load: 100 users, 10 spawn rate, 5 minutes
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --headless \
    -u 100 \
    -r 10 \
    -t 5m
```

### Using Makefile

```bash
# Run load tests (interactive)
make test-load

# Run quick load test
make test-load-quick

# Run full load test suite
make test-load-full
```

## Test Scenarios

### AnonymousUser (Weight: 3)

Simulates unauthenticated users:
- Health check endpoint (high frequency)
- Detailed health check
- OpenAPI schema fetch
- Failed login attempts (rate limiting test)

### AuthenticatedUser (Weight: 1)

Simulates logged-in users:
- User profile fetch
- Todo CRUD operations (list, create, read, update, delete)

### AdminUser (Weight: 0, disabled by default)

Simulates admin users:
- User management operations

### StressTestUser (Weight: 0, disabled by default)

For stress testing with minimal wait times.

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TEST_USER_EMAIL` | Email for authenticated tests | Random |
| `TEST_USER_PASSWORD` | Password for authenticated tests | `LoadTest123!` |
| `ADMIN_EMAIL` | Admin user email | `admin@example.com` |
| `ADMIN_PASSWORD` | Admin user password | `adminpass123` |
| `LOCUST_HOST` | Target host | `http://localhost:8000` |

### Example with Auth

```bash
export TEST_USER_EMAIL="loadtest@example.com"
export TEST_USER_PASSWORD="mypassword123"

locust -f tests/load/locustfile.py --host=http://localhost:8000 --headless -u 20 -r 5 -t 1m
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `-f FILE` | Locustfile to use |
| `--host HOST` | Host to load test |
| `--headless` | Run without web UI |
| `-u USERS` | Number of concurrent users |
| `-r RATE` | Spawn rate (users per second) |
| `-t TIME` | Test duration (e.g., 30s, 5m, 1h) |
| `--html REPORT` | Generate HTML report |
| `--csv PREFIX` | Generate CSV reports |

## Output Reports

### HTML Report

```bash
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --headless \
    -u 50 -r 5 -t 2m \
    --html=reports/load_test_report.html
```

### CSV Reports

```bash
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --headless \
    -u 50 -r 5 -t 2m \
    --csv=reports/load_test
```

This generates:
- `reports/load_test_stats.csv` - Request statistics
- `reports/load_test_stats_history.csv` - Statistics over time
- `reports/load_test_failures.csv` - Failed requests

## Performance Targets

Typical performance targets for this API:

| Metric | Target | Critical |
|--------|--------|----------|
| Response Time (p50) | < 100ms | < 500ms |
| Response Time (p95) | < 500ms | < 2000ms |
| Response Time (p99) | < 1000ms | < 5000ms |
| Error Rate | < 0.1% | < 1% |
| Throughput | > 100 RPS | > 50 RPS |

## Distributed Testing

For larger tests, run Locust in distributed mode:

### Master Node

```bash
locust -f tests/load/locustfile.py --master
```

### Worker Nodes

```bash
locust -f tests/load/locustfile.py --worker --master-host=MASTER_IP
```

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
- name: Run Load Tests
  run: |
    locust -f tests/load/locustfile.py \
      --host=${{ secrets.TEST_API_URL }} \
      --headless \
      -u 20 -r 2 -t 1m \
      --html=load_test_report.html

- name: Upload Load Test Report
  uses: actions/upload-artifact@v3
  with:
    name: load-test-report
    path: load_test_report.html
```

## Troubleshooting

### Common Issues

1. **Connection refused**: Ensure the API server is running
2. **Auth failures**: Check TEST_USER credentials
3. **Rate limiting**: Reduce spawn rate or increase wait times
4. **Memory issues**: Reduce number of users or test duration

### Debug Mode

```bash
# Enable verbose logging
locust -f tests/load/locustfile.py --host=http://localhost:8000 --loglevel DEBUG
```
