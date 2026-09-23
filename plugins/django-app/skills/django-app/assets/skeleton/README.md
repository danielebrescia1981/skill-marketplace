# MyApp

## Quick start

```bash
cp .env.example .env
just setup        # deps, Tailwind binary, vendored JS, Postgres, migrations
just superuser you@example.com
just dev          # https://myapp.localhost/
```

Needs: [uv](https://docs.astral.sh/uv/), [just](https://just.systems), Docker, and [portless](https://www.npmjs.com/package/portless) (`npm i -g portless`) for local HTTPS.

## More

- `just` lists every task.
- Engineering docs: [`docs/`](docs/). Agent instructions: [`CLAUDE.md`](CLAUDE.md).
