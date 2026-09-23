# Background tasks, email, cache, storage

**Load:** in Create mode unless the app sends no email and does no background work.

## Procrastinate (Postgres-backed queue)

No Celery, no Redis, no broker. All four Django repos use Procrastinate.

```python
INSTALLED_APPS += ["procrastinate.contrib.django"]
PROCRASTINATE_IMPORT_PATHS = ["config.tasks", "documents.tasks"]   # every module holding @app.task
```

```python
from procrastinate.contrib.django import app

@app.task(queue="emails", retry=5, name="send_email")
def send_email_task(payload: dict): ...

@app.periodic(cron="0 2 * * *", periodic_id="daily_cleanup")
@app.task(queue="maintenance", name="daily_cleanup")
def daily_cleanup(timestamp: int): ...

send_email_task.defer(payload=...)           # from views / services
```

- Queues by purpose: `emails`, `default`, `maintenance`, and a named queue for heavy work (`signing`, `ocr`).
- Use `lock=` for tasks that must not overlap, and `queueing_lock=` to dedupe enqueues.
- Worker is the same image as web with a different command (`python manage.py procrastinate worker`). In dev it's one of the `just dev` processes.
- Tenant-scoped tasks take `tenant_id` and run inside `tenant_context` (tenancy-rls.md). The worker connects as admin **only** for truly cross-tenant jobs.
- Tests: run tasks inline (`procrastinate` in-memory connector, or call the function directly). On an SQLite-only test setup (not allowed with RLS) set `MIGRATION_MODULES["procrastinate"] = None` and mock `.defer`.
- Admin visibility: a small admin dashboard over `procrastinate_jobs` (meetingsignals custom `AdminSite`) pays for itself the first time email stops going out.

## Email

**Queue every send.** Web requests never wait on SMTP/SES, and failures retry. On **Django 6.1+ use `MAILERS`**. `EMAIL_BACKEND`/`EMAIL_HOST` are deprecated (removed in 7.0), and 6.1 adds a deploy check (`mail.E001`) that fails on a dev-only backend:

```python
MAILERS = {
    "default":   {"BACKEND": "config.email_backends.ProcrastinateEmailBackend"},   # what allauth & app code use
    "transport": {"BACKEND": "django_ses.SESBackend"},                             # what the worker sends through
}   # dev: transport = SMTP to Mailpit with OPTIONS {"host": ..., "port": 1025}
```

`ProcrastinateEmailBackend.send_messages` serialises each message (to, subject, body, alternatives, headers) and `.defer()`s `send_email_task`. The task builds the message with `connection=mailers["transport"]`; the default mailer would re-queue it. Attachments either go direct through `transport` or are stored and linked. The skeleton has both (`src/config/email_backends.py`, `tasks.py`). Older repos (eqms, gxpsign, appsfolio) use the pre-6.1 `EMAIL_BACKEND` + `ACTUAL_EMAIL_BACKEND` pair to do the same thing.

- **Dev: Mailpit** (`axllent/mailpit` in `docker-compose.yml`, SMTP on 1025, UI on 8025). Real HTML rendering, and e2e tests read it over its HTTP API. Console backend only in unit tests.
- **Prod: Amazon SES** via `django-ses[events]`. The bounce/complaint SNS webhook goes at `/ses/events/` (`SESEventWebhookView`, which verifies the SNS signature, tenant-exempt), with signal receivers that log and suppress bounced addresses.
- `DEFAULT_FROM_EMAIL = formataddr((PRODUCT_NAME, f"noreply@{MAIL_DOMAIN}"))`. Don't double-wrap when the env value already has a display name.
- `EMAIL_SUBJECT_PREFIX` / allauth subject prefix per env: `[MyApp TEST] `, `[MyApp DEV] `. Empty in prod.
- `LAUNCH.md` item: SES production access, DKIM/SPF/DMARC on `MAIL_DOMAIN`.

## Cache

`DatabaseCache` on Postgres, created by migration or `createcachetable` in `just setup`. gxpsign makes the table `UNLOGGED` (a management command) for speed, since the data is disposable. Used for rate limits and single-use tokens.

Why not LocMem: each gunicorn worker gets its own copy, so every "N per hour" limit is silently multiplied by the worker count (refractions comment). If a rate limiter must stay on LocMem for now, say so in a `ponytail:` comment naming the ceiling.

## File storage

```python
USE_S3 = env.bool("USE_S3", default=False)
STORAGES = {
    "default": {"BACKEND": "storages.backends.s3.S3Storage"} if USE_S3
               else {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
AWS_DEFAULT_ACL = "private"
AWS_QUERYSTRING_AUTH = False      # files go through an app view — authz + integrity check on every download
```

- Cloudflare R2 (S3 API) or S3. Path per tenant: `tenants/<slug>/<model>/<uuid>/<filename>`.
- Serve private files through a view that checks permission (and re-verifies a stored SHA-256 for GxP records), not with presigned URLs, unless the files are big enough that streaming through Django hurts.
- Upload limits: `DATA_UPLOAD_MAX_MEMORY_SIZE` plus an app-level `DOCUMENT_UPLOAD_MAX_BYTES` check in the form.

## PDFs (only if needed)

WeasyPrint for HTML→PDF, pyHanko for PAdES signatures, headless LibreOffice (`libreoffice-writer` plus metric-compatible fonts) for DOCX→PDF fidelity. Each adds OS packages to the runtime image. On macOS, the justfile exports `DYLD_LIBRARY_PATH` (justfile.md).
