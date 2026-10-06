# Cookie auth and CSRF contract

Browser frontends authenticate with httpOnly JWT cookies. They do not store
tokens in `localStorage`. Non-browser clients keep using
`Authorization: Bearer <access>`. The backend is API-only: the frontend runs
in a separate container or origin.

Code: `core/security/cookie_auth.py` (middleware and cookie helpers) and
`core/controllers/session_controller.py` (CSRF, refresh, logout).

## Cookies

| Cookie | Set by | Readable by JS | Path | SameSite | Secure | Lifetime |
|---|---|---|---|---|---|---|
| `csrftoken` | `GET /api/auth/csrf` | yes | `/` | Lax | `USE_TLS` | 1 year |
| `access_token` | login, refresh | no (httpOnly) | `/api/` | Lax | `USE_TLS` | `ACCESS_TOKEN_LIFETIME` (60 min) |
| `refresh_token` | login, refresh | no (httpOnly) | `/api/auth/` | Lax | `USE_TLS` | `REFRESH_TOKEN_LIFETIME` (7 days) |

**Cookie auth needs TLS outside localhost.** Browsers keep `Secure` cookies
only on HTTPS origins and on `localhost`; on any other plain-HTTP host they
drop them, so cookie login fails. Cookies without `Secure` would travel in
clear text. So production settings (`api.settings.prod`) refuse to start
unless `USE_TLS=true`, and then every auth, session and CSRF cookie is
`Secure`. Put a TLS proxy in front of Django (or of the bundled nginx, which
passes the proxy's `X-Forwarded-Proto: https` through).
`ALLOW_INSECURE_COOKIES=true` lets the production settings run over plain HTTP
for a local smoke run only; `ENVIRONMENT=production` rejects it.
Development serves `http://localhost`, where `USE_TLS=false` works.

Login endpoints that set the auth cookies: `POST /api/auth/login`,
`POST /api/auth/login/username`, `POST /api/auth/passwordless/login/verify`,
`POST /api/auth/otp/verify` (purpose `LOGIN`), and
`POST /api/auth/otp/verify-token`. They also return the tokens in the body
for bearer clients. Browser clients ignore those fields.

## Client rules

1. Call `GET /api/auth/csrf` once before login. It needs no auth and has no
   side effect except the cookie. It returns `{"csrfToken": "..."}`.
2. Send every request with credentials (`fetch(url, { credentials: "include" })`).
3. On every `POST`, `PUT`, `PATCH`, and `DELETE`, including `/api/auth/login`
   and `/api/auth/refresh`, send `X-CSRFToken` equal to the current
   `csrftoken` cookie value.
4. A missing or wrong token returns `403`:

   ```json
   {"error": true, "message": "CSRF check failed. Fetch /api/auth/csrf and retry.", "code": "csrf_failed"}
   ```

   On `403` with `code` `csrf_failed`, call `GET /api/auth/csrf` once and
   retry the request once. Do not loop.
5. On `401` from a protected endpoint, call `POST /api/auth/refresh` with an
   empty JSON body (`{}`) and the CSRF header, then retry once. Refresh
   rotates both cookies and blacklists the old refresh token. In cookie mode
   it returns `{"access": null, "refresh": null}`: the new tokens are only in
   the cookies. If refresh returns `401`, the session is over; send the user
   to login. A second tab that refreshes with the same cookie at the same
   moment gets `401` while the browser already holds the new cookie from the
   first response; retry once before you log the user out. See
   [Refresh token reuse](#refresh-token-reuse).
6. Log out with `POST /api/auth/logout`, body `{}`, and the CSRF header. It
   blacklists the refresh token from the cookie and clears both auth
   cookies. It needs no access token, so it works after the access cookie
   has expired. If an access token is present, the refresh token must belong
   to the same user (`400` otherwise).
7. Server-Sent Events: `new EventSource("/api/events/stream/", { withCredentials: true })`.
   The access cookie authenticates the stream.

## Bearer clients

A request that sends `Authorization` or `X-API-Key` and no auth cookie skips
the CSRF check, because a browser never adds those headers to a cross-site
request on its own. A request that carries `access_token` or
`refresh_token` is always CSRF-checked, whatever headers it adds.

- Get tokens: `POST /api/token/pair` (CSRF-exempt, body tokens only).
- Refresh: `POST /api/token/refresh` (CSRF-exempt), or
  `POST /api/auth/refresh` with `{"refresh": "..."}` in the body plus CSRF.
- `/api/auth/login` is not exempt. Bearer clients call
  `GET /api/auth/csrf` first or use `/api/token/pair`.

`API_CSRF_EXEMPT_PATHS` lists the exempt prefixes (default `["/api/token/",
"/api/billing/webhooks/"]`). Add each signed webhook receiver there: it
verifies the sender's signature instead of a CSRF token.

## Refresh token reuse

Every refresh (`/api/auth/refresh` and `/api/token/refresh`) blacklists the
presented refresh token and issues a new one
(`core/security/refresh_tokens.py`).

- A blacklisted refresh token presented within `REUSE_GRACE_SECONDS` (30
  seconds) of its rotation gets `401` and nothing else. Two tabs that share
  one cookie jar, a React StrictMode double effect, or a retried fetch cause
  this; the browser already holds the successor cookie.
- After the grace window, the API cannot tell the real client from someone
  who copied the token. It returns `401` and revokes every outstanding
  refresh token of that user, on every device.

The trade-off: an attacker who uses a stolen token first, and the real
client's replay arrives within 30 seconds, keeps the session until the next
reuse or password change.

Every password change also revokes all refresh tokens of the user: the OTP
password reset, the admin password form, `manage.py changepassword`, and any
code that calls `set_password()` and then `save()`.

Access tokens are not revoked. They stay valid until `ACCESS_TOKEN_LIFETIME`
(60 minutes) ends.

## Login lockout

`core/security/brute_force.py` counts failed password logins on
`/api/auth/login`, `/api/auth/login/username`, `/api/token/pair`, and the
admin login form. All four share one counter per account (a known username
counts against its email). Five failures for one account from one client IP,
or 20 failures from one client IP for any accounts, inside five minutes lock
that (account, IP) pair or that IP for 15 minutes. Locked requests get `429`
(admin: plain-text `429`), even with the right password. The lock never
covers the account as a whole, so an attacker cannot lock the owner out from
another address. Unknown accounts lock the same way, so a lockout tells
nothing about which accounts exist. Guessing from many addresses is limited
per address only: add MFA or a CAPTCHA if that matters for your platform.

### Client IP and `NINJA_NUM_PROXIES`

The client IP is `REMOTE_ADDR` unless `NINJA_NUM_PROXIES` is set: then it is
the `X-Forwarded-For` entry that the outermost trusted proxy added
(`api/utils/http.py`). Set it to the number of proxies that append to
`X-Forwarded-For`. Too low, and every client shares the proxy's IP, so 20
failed logins from anyone lock logins for everyone. Too high, and clients
choose their own IP.

| Deployment | Value |
|---|---|
| Development (`runserver`, no proxy) | `0` (default) |
| Compose `prod` profile: TLS proxy, then the bundled nginx | `2` (Compose default) |
| Single image behind one platform router, such as Heroku, which appends the client IP | `1` (image default) |
| Each extra hop that appends, such as a CDN | add `1` |

Other platforms differ: check what your router adds, for example by echoing
`X-Forwarded-For` from a test request, before you pick the value.

## Account enumeration

These answers are the same for known and unknown accounts:

- `POST /api/auth/signup` returns `202` with
  `{"message": "Check your email to finish signing up.", "success": true}`.
  A new email and username create the account and send a welcome email. A
  taken email sends its owner a notice. A taken username creates nothing and
  emails the address to choose another username. Password validation errors
  (`400`) depend only on the submitted values.
- `POST /api/auth/passwordless/login/request` and the OTP request endpoints
  return the same message whether or not the account exists.
- `POST /api/auth/login/username` hashes the password for an unknown
  username too, so timing does not reveal which usernames exist.

Account emails go out on a background thread (`send_account_email`), so the
response time does not depend on mail delivery. Set `ACCOUNT_EMAIL_SYNC=True`
in settings to send inline (the test settings do).

## Settings

All in `api/settings/common.py`:

| Setting | Value |
|---|---|
| `USE_TLS` | env, default `false`. Turns on `Secure` cookies; prod also turns on HTTPS redirect, HSTS and the `X-Forwarded-Proto` header. Production requires `true`. |
| `ALLOW_INSECURE_COOKIES` | env, default `false`. Lets prod settings run with `USE_TLS=false` for a local smoke run; rejected with `ENVIRONMENT=production`. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD` | env, default `false` (prod). HSTS itself is one year whenever `USE_TLS=true`. |
| `CSRF_COOKIE_HTTPONLY` | `False` |
| `CSRF_COOKIE_SAMESITE` | `"Lax"` |
| `CSRF_COOKIE_SECURE` | `USE_TLS` |
| `CSRF_TRUSTED_ORIGINS` | env, default `[FRONTEND_URL]` |
| `CORS_ALLOWED_ORIGINS` | env, default `[FRONTEND_URL]` |
| `CORS_ALLOW_CREDENTIALS` | `True` |
| `CORS_ALLOW_HEADERS` | includes `authorization`, `content-type`, `x-csrftoken` |
| `AUTH_COOKIE_*` | names, paths, `SameSite=Lax`, `Secure=USE_TLS` |
| `NINJA_NUM_PROXIES` | env, default `0`. Trusted proxies for the client IP (throttles, lockout, audit). |
| `ADMIN_URL` | env, default `admin/`. Admin mount path. Update the nginx `location` regex when you change it. |
| `API_DOCS` | env: `public` (default), `staff` (admin login), or `off` (production default). Controls `/api/docs` and `/api/openapi.json`. |

## Cross-origin development

`SameSite=Lax` cookies reach the API only when the frontend and the API are
the same site. `localhost:3000` and `localhost:8000` are the same site;
`localhost` and `127.0.0.1` are not. Prefer the frontend dev server proxy
(for example Vite `server.proxy` for `/api`) so the browser sees one origin.
Keep `FRONTEND_URL` equal to the origin in the browser address bar, because
Django checks the `Origin` header against `CSRF_TRUSTED_ORIGINS`.
The development settings default `CORS_ALLOWED_ORIGINS` and
`CSRF_TRUSTED_ORIGINS` to `FRONTEND_URL` plus the `localhost` and `127.0.0.1`
origins on ports 3000 and 5173 (Vite). A value in `.env` replaces the default.
