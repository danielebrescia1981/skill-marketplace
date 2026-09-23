# Frontend — Tailwind v4 standalone, HTMX, Alpine, templates, /help/

**Load:** when the app has server-rendered UI (almost always). Skip for API-only services.

## Stack

- **Tailwind v4, standalone CLI, pinned.** No Node in dev or in the image. `just tailwind-setup` downloads the binary for `TAILWIND_VERSION` into `bin/` (gitignored). In Docker, download the Linux binary in a build stage. Don't use the in-browser `@tailwindcss/browser` build (meetingsignals); it ships a compiler to every visitor and breaks under CSP.
- **HTMX 2 + Alpine 3, vendored** in `static/vendor/` with the version in the filename (`htmx-2.0.4.min.js`, `alpine-3.14.9.min.js`). Vendoring lets CSP stay `script-src 'self' 'nonce-…'`. Floating CDN tags like `alpinejs@3.x.x` are how a supply-chain change lands unreviewed. If you must use a CDN, pin exactly and add SRI.
- **crispy-forms + crispy-tailwind** for forms. **django-htmx** for `request.htmx`.
- Self-host fonts.

`static/css/input.css`:

```css
@import "tailwindcss";
@plugin "@tailwindcss/forms";              /* first-party plugins are bundled in the standalone CLI */
@source "../../templates";
@source "../../src";                       /* class names built in Python (widgets, template tags) */
@theme {
  --color-brand-600: oklch(0.55 0.15 250);
  --font-sans: "Inter", system-ui, sans-serif;
}
@layer components { .btn { @apply inline-flex items-center rounded-md px-3 py-2 text-sm font-medium; } }
```

`output.css` is generated and gitignored. Pass `--ignore input.css` to `collectstatic`: its `@import "tailwindcss"` breaks manifest post-processing.

Design tokens live in `DESIGN.md` (use the `design-md` skill), and `@theme` mirrors them.

## Templates

- Project-level `templates/`. `templates/<app>/<object>_<action>.html` for pages, `templates/<app>/partials/_<thing>.html` for HTMX fragments. Fragment endpoints return partials only.
- Two bases when there's a marketing site: `templates/base.html` (app shell) and `templates/website/base.html` (marketing).
- `templates/components/`: toast, confirm modal, empty state, pagination.
- `templates/errors/404.html`, `500.html`. The 500 handler passes `sentry_event_id` so the page can open Sentry's feedback widget.
- `templates/emails/<name>.txt` + `.html` pairs.
- Navigation comes from one source (`config/nav.py`), exposed through a context processor. No hand-maintained nav in several templates.

CSRF for HTMX, once, on `<body>`:

```html
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

`CSRF_COOKIE_HTTPONLY = False` only if JS reads the cookie; the header approach above doesn't need it.

Messages as toasts: messages render into a partial that HTMX responses include as an out-of-band swap (`hx-swap-oob`), so both full-page and fragment requests show them (appsfolio `_toast_oob.html`).

Dev reload: `django-browser-reload` and `debug-toolbar`, both only under `DEBUG`. Hide the toolbar in e2e.

## Marketing site and /help/ (Q7)

One container serves `/` (marketing), `/help/` (user docs) and the app. Nothing extra to deploy.

- **Help docs**: Markdown in `help/`, built with **Zensical** (`uvx zensical build`; config in `zensical.toml` with `docs_dir = "help"`, `site_dir = "help_site"`, `site_url = "/help/"`). Build it in a Docker builder stage and copy it in. Use `uvx` so the docs generator never enters the app's dependency tree. Serve it through `STATICFILES_DIRS += [("help", BASE_DIR / "help_site")]` plus a small view that maps `/help/<path>/` to `index.html` with a path-traversal check. Give `/help/` its own looser CSP if the theme needs it.
- **In-app help links**: a template tag `{% help_url "training" "anchor" %}` deep-links `?` icons. A test asserts every referenced anchor exists in the built site (eqms).
- **Marketing**: `website` app with its own base template, or static files under `public/` served by `WHITENOISE_ROOT` (appsfolio). If marketing lives at `/`, put the app under `/app/` (appsfolio) or on the tenant subdomains.
- **Changelog**: customer-facing, one entry per prod release. Keep it in `help/changelog.md` or as dataclasses in code (refractions `changelog_data.py`) when the site renders it.

Pick one docs tool per repo. meetingsignals builds with mkdocs in Docker and Zensical in the justfile, which is drift.

## Accessibility and polish

Run the `impeccable`/`audit` skills on key screens before launch. Minimum: labelled inputs, focus rings kept, colour contrast within the `@theme` tokens, and `hx-indicator` on anything slower than ~300 ms.
