# Security hardening and launch checklist

**Load:** before the first external user, and at each pre-launch review. Most of this is already in `assets/skeleton/src/config/settings.py`; this module is for checking and explaining it.

## One switch

```python
HARDENED = env.bool("SECURITY_HARDENING", default=not DEBUG)
```

`HARDENED` drives SSL redirect, HSTS and secure cookies, and every individual setting stays env-overridable for the odd case (eqms). Tests assert the prod posture by overriding `HARDENED`.

## Settings

| Setting | Value | Why |
|---|---|---|
| `SECURE_SSL_REDIRECT` | `HARDENED` (or leave to Traefik) | with `SECURE_REDIRECT_EXEMPT = [r"^ht/$", r"^ping/$"]` so health checks work over HTTP |
| `SECURE_PROXY_SSL_HEADER` | `("HTTP_X_FORWARDED_PROTO", "https")` | behind Traefik |
| `SECURE_HSTS_SECONDS` | `31536000 if HARDENED else 0` | + `INCLUDE_SUBDOMAINS`, `PRELOAD` once every subdomain is HTTPS |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | `HARDENED` | |
| `SESSION_COOKIE_HTTPONLY` | `True` | |
| `SESSION_COOKIE_SAMESITE` | `"Lax"` | Strict breaks SSO callbacks and emailed links |
| `SESSION_COOKIE_AGE` | 8 h (hardened) | shorter for sensitive apps; per-tenant idle timeout via middleware |
| `SESSION_COOKIE_DOMAIN` / `CSRF_COOKIE_DOMAIN` | `.{BASE_DOMAIN_NAME}` for tenant subdomains | set a distinct cookie *name* per env so test and prod on sibling domains don't collide |
| `CSRF_TRUSTED_ORIGINS` | derived: `https://{BASE}`, `https://*.{BASE}` | |
| `X_FRAME_OPTIONS` | `"DENY"` | |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | |
| `SECURE_REFERRER_POLICY` | `"same-origin"` | |
| `SECURE_CROSS_ORIGIN_OPENER_POLICY` | `"same-origin"` | |
| `DEBUG` in prod | `raise ImproperlyConfigured` if `APP_ENVIRONMENT == "prod" and DEBUG` | appsfolio guard |
| `ALLOWED_HOSTS` | derived + loopback | |
| Password validators | min length 12 (+ complexity for GxP) | |

## CSP with nonces

Django 6 has built-in CSP (`django.middleware.csp.ContentSecurityPolicyMiddleware`, `SECURE_CSP` / `SECURE_CSP_REPORT_ONLY`, `{{ csp_nonce }}`). Prefer it over the hand-rolled `SecurityHeadersMiddleware` in eqms, and check the current docs with context7 before wiring it.

```python
from django.utils.csp import CSP
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF, CSP.NONCE],
    "img-src": [CSP.SELF, "data:"],
    "connect-src": [CSP.SELF] + (["https://*.ingest.sentry.io"] if SENTRY_DSN else []),
    "frame-ancestors": [CSP.NONE],
    "form-action": [CSP.SELF],   # + IdP hosts if SSO posts cross-site
}
```

Start as `SECURE_CSP_REPORT_ONLY` in test, watch the reports, then enforce. Vendored JS (frontend.md) is what makes `'self'` workable. Alpine's standard build needs `'unsafe-eval'`, so use `@alpinejs/csp` if you enforce without it.

## Middleware guards

App-wide middleware beats per-view mixins you'll forget on the next view:

- `NoCacheAuthenticatedMiddleware`: `Cache-Control: no-store` on responses to logged-in users.
- `ReadOnlyRoleMiddleware`: Reader role gets 403 on unsafe methods, except its own `/accounts/`, `/sso/`, and token pages.
- `RateLimitMiddleware`: path rules like `("/accounts/login/", 10, 300)` on the **DB cache**. Take the client IP from the proxy's header only when the proxy overwrites it. A raw first `X-Forwarded-For` hop is client-controlled (meetingsignals). Or use `django-ratelimit` decorators on the few sensitive views.
- `SessionInactivityTimeoutMiddleware` when idle timeout matters.

## Forms and flows

- Contact/signup spam: honeypot field + signed timestamp (`signing.dumps`, minimum fill time, maximum age) + blocked-domain list. Spam gets the normal success response, silently dropped (meetingsignals).
- Magic links and invites: signed, expiring, single-use, with verify and spend as separate steps so link scanners don't burn them.
- `ACCOUNT_LOGOUT_ON_GET = False`, `ACCOUNT_CONFIRM_EMAIL_ON_GET = False`.
- Uploads: size cap, content-type allowlist, stored outside `STATIC_ROOT`, served through a view.
- `/.well-known/change-password` redirect (password managers).
- `robots.txt` disallows `/admin/`, `/app/`, `/accounts/`.
- Admin at a non-default path if it's internet-exposed, staff behind MFA.

## Secrets

- Only in env / the server `.env`. `.env.example` is committed with every key and no values.
- Required secrets fail boot when `DEBUG` is off (foundation.md). Build-time dummies live on the `collectstatic` RUN line only.
- No real defaults for `SECRET_KEY` or `SENTRY_DSN` in settings (gxpsign has a hardcoded DSN default).
- `FERNET_KEYS` as a list for rotation. Encrypt IdP secrets and recoverable tokens at rest.
- Pre-commit `detect-private-key`, plus `git-secrets` hooks if you have them (appsfolio).

## Dependencies and supply chain

- `uv.lock` committed, `uv sync --frozen` in Docker/CI.
- Actions pinned by SHA, CDN JS pinned exactly (or vendored), Tailwind binary pinned by version.
- `uv run bandit -r src -q` and `uvx pip-audit` periodically, or as a CI job once the backlog is clean.

## Launch checklist (copy into LAUNCH.md)

🔴 = blocks launch.

- 🔴 CI gate green; prod deploy via promote-by-digest; `/ht/` verified after deploy
- 🔴 `check --deploy` clean with prod settings (a test enforces it)
- 🔴 [tenant] app DB role is NOBYPASSRLS, non-owner, and the RLS meta-test passes against prod-like migrations
- 🔴 Backups running off-box **and a restore tested**
- 🔴 Sentry receiving from prod; uptime monitor on `/ht/`
- 🔴 SES production access; SPF/DKIM/DMARC on the mail domain; bounce webhook subscribed
- 🔴 [stripe] live keys, live webhook endpoint + secret, Customer Portal configured in live mode
- 🔴 [sso] tested against at least one real IdP of each type offered (docs/SSO_TESTING.md)
- 🟡 CSP enforced (not report-only); HSTS preload submitted
- 🟡 Privacy policy / terms / cookie notice pages; DPA template if B2B
- 🟡 [gxp] IQ/OQ executed on prod, VSR signed, release memo filed
- 🟢 Rate limits reviewed against real traffic; pip-audit clean
