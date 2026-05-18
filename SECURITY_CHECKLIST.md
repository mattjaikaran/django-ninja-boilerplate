# Shipping Security Checklist

Run through this before every production deploy. Each item maps to a real attack vector.

---

## Privacy & Data Handling

- [ ] Do you collect any user data (email, name, IP, device info)?
  - If yes: add a privacy policy page linked from your signup flow and footer
  - Minimum: state what you collect, why, how long you keep it, and who can request deletion
- [ ] Know exactly where user data is stored: which DB, which cloud region, which S3 bucket
  - Document this in your deploy runbook — you need it for GDPR/CCPA deletion requests
- [ ] PII fields (email, name, phone) are never written to logs
  - `AUDIT_LOG_BODY = False` (default in this boilerplate) keeps request bodies out of logs
  - `log_api_call` scrubs `password`, `token`, `api_key`, and other sensitive fields before logging
- [ ] Verify `AUDIT_LOG_BODY=False` in production `.env`

---

## Security Headers

Run `make security-check` (calls `manage.py check --deploy`) before each deploy.

- [ ] `X-Frame-Options: DENY` — prevents clickjacking (`X_FRAME_OPTIONS = "DENY"` ✓ in common.py)
- [ ] `X-Content-Type-Options: nosniff` — stops MIME sniffing (`SECURE_CONTENT_TYPE_NOSNIFF = True` ✓)
- [ ] `Strict-Transport-Security` — forces HTTPS for 1 year (`SECURE_HSTS_SECONDS = 31536000` ✓ in prod.py)
- [ ] `Referrer-Policy: strict-origin-when-cross-origin` ✓ in prod.py
- [ ] `Content-Security-Policy` — configured via django-csp ✓
  - Dev: report-only mode, permissive (won't block your local tools)
  - Prod: enforced, no `unsafe-inline` or `unsafe-eval`
  - Tighten `CSP_SCRIPT_SRC` / `CSP_STYLE_SRC` in `prod.py` as your frontend stabilises
- [ ] `SESSION_COOKIE_HTTPONLY = True` and `SESSION_COOKIE_SECURE = True` (prod.py ✓)
- [ ] `CSRF_COOKIE_HTTPONLY = True` (prod.py ✓)

Verify headers on a live deployment:

```bash
curl -I https://yourdomain.com/api/health/
```

---

## OWASP Top 10 Basics

- [ ] **SQL Injection** — Django ORM uses parameterized queries throughout. Never interpolate user
  input into raw SQL. If you add `raw()` or `cursor.execute()`, use `%s` placeholders only.
- [ ] **XSS** — API returns JSON, not HTML, so XSS surface is small. Admin uses Django templates
  (auto-escaped). If you add any template rendering, never use `mark_safe()` on user input.
- [ ] **Broken Auth** — JWT tokens expire (60 min access, 1 day refresh). Brute force lockout
  fires after 5 failed attempts, 15-minute lockout (`core/security/brute_force.py`).
- [ ] **Sensitive Data Exposure** — `UserSchema` does not expose `password`. Check any new schema
  you add: no `password`, `token`, or key fields in response schemas.
- [ ] **Security Misconfiguration** — `DEBUG=False` in prod. `ALLOWED_HOSTS` set. `SECRET_KEY`
  is a real secret, not the default. Run `manage.py check --deploy` to catch common misconfigs.
- [ ] **Insecure Dependencies** — `pip-audit` runs on pre-push. Also run `make ci-security` in CI.

---

## Secrets & Environment Variables

- [ ] `.env` is in `.gitignore` — never committed
- [ ] `.env.example` has placeholder values only, not real secrets
- [ ] `SECRET_KEY` is unique per environment (generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- [ ] `DB_PASSWORD`, `REDIS_URL`, `CELERY_BROKER_URL` are set per-environment
- [ ] `STRIPE_SECRET_KEY`, `AWS_SECRET_ACCESS_KEY`, `CENTRIFUGO_API_KEY` are never hardcoded
- [ ] Rotate any secret that was ever committed to git history (use `git-filter-repo` to scrub)
- [ ] CI/CD secrets stored in GitHub Actions secrets or equivalent vault — not in workflow YAML

Quick scan for accidentally committed secrets:

```bash
git log --all --oneline | head -20
git grep -i "password\|secret_key\|api_key" -- '*.py' '*.env' '*.yml'
```

---

## API Response Audit

Check that no endpoint leaks sensitive fields. For each new model/schema you add:

- [ ] No `password` or `password_hash` field in any response schema
- [ ] No raw `token` values in list endpoints (only return them at creation time)
- [ ] No internal IDs, foreign keys, or infrastructure details in error messages
- [ ] Error responses use generic messages in production (`DEBUG=False` strips stack traces ✓)

Spot-check with:

```bash
# Should return user info WITHOUT password field
curl -H "Authorization: Bearer <token>" https://yourdomain.com/api/auth/me
```

---

## Secrets in Logs

The `log_api_call` decorator scrubs these fields before writing to logs:
`password`, `token`, `access_token`, `refresh_token`, `secret`, `api_key`, `private_key`, `authorization`, `credit_card`, `ssn`

- [ ] If you add a new sensitive field to any schema, add it to `SENSITIVE_FIELDS` in `api/decorators.py`
- [ ] Verify structured logs in production do not contain raw credential values:
  ```bash
  docker logs <container> 2>&1 | grep -i "password\|secret\|token" | head -20
  ```
- [ ] `django.db.backends` log level is `WARNING` in production (prevents SQL query logging ✓)

---

## API Keys & Frontend Code

- [ ] No secret API keys in any frontend `.js` / `.ts` file
- [ ] Only **publishable** keys (e.g. `STRIPE_PUBLISHABLE_KEY`) belong on the frontend
- [ ] Secret keys (`STRIPE_SECRET_KEY`, `AWS_SECRET_ACCESS_KEY`) are server-side only, accessed
  via `settings.py` from environment variables
- [ ] If your frontend calls a third-party API directly, proxy it through your Django backend instead
- [ ] Centrifugo tokens are generated server-side and scoped per-user (`api/centrifugo.py` ✓)

---

## Rate Limiting

Rate limiting is configured at two levels in this boilerplate:

**Global throttling** (django-ninja-extra, `common.py`):
- Authenticated users: 1000 req/day
- Anonymous: 100 req/day

**Per-endpoint** (`@rate_limit` decorator):
- `POST /auth/signup` — 10 req/min
- `POST /auth/login` — 20 req/min
- `POST /auth/passwordless/login/request` — 5 req/min

**Brute force lockout** (`core/security/brute_force.py`):
- Login locked after 5 failed attempts for 15 minutes

Before launching:
- [ ] Confirm Redis is running and cache backend is connected (rate limits degrade gracefully if Redis is down, but won't protect you)
- [ ] Add `@rate_limit` to any endpoint that sends email, creates a resource, or calls a paid external API
- [ ] Consider tightening `THROTTLE_RATES["anon"]` for public-facing APIs

---

## Pre-Deploy Commands

```bash
# Static analysis + security scan
make lint
make security-check        # manage.py check --deploy
make ci-security           # pip-audit for known CVEs

# Verify headers on staging
curl -I https://staging.yourdomain.com/api/health/

# Confirm no DEBUG mode
grep DEBUG .env.production

# Rotate secrets if any were ever exposed
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## Optional but Recommended

- [ ] Enable email verification (`is_verified` field exists on `User` model — enforce it on signup)
- [ ] Add `django-axes` or extend `core/security/brute_force.py` for admin login protection
- [ ] Set up Sentry or equivalent error tracking with PII scrubbing enabled
- [ ] Add a `robots.txt` that disallows `/admin/`
- [ ] Review and tighten CSP `connect-src` once you know all your third-party API domains
