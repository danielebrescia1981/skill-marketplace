# Repo management — branches, commits, docs, agent config

**Load:** always in Create mode; Audit mode. **Assets:** `assets/skeleton/CLAUDE.md`, `assets/skeleton/dot-gitignore`, `assets/skeleton/dot-pre-commit-config.yaml`.

## Branches and promotion

`dev → test → main`. Work on `dev`. Nothing is committed directly to `test` or `main`.

| Branch | Deploys | How |
|---|---|---|
| `dev` | nowhere (local) | daily work |
| `test` | test env, automatically on push | `git checkout test && git merge --ff-only dev && git push && git checkout dev` |
| `main` | production, **manually** | merge `test` (not `dev`) into `main`, then `gh workflow run deploy-prod.yml --ref main -f version=vX.Y.Z` |

Merge `test` into `main`, not `dev`, so prod ships exactly what test ran. Version tags are created by the prod workflow after a verified deploy — never by hand.

## Commits

- Conventional prefix with scope: `feat(records):`, `fix(security):`, `ci(test):`, `docs:`, `perf:`, `security:`.
- **The subject says what changed for the user**, not the code: `fix: lookalike email domains could auto-join a stranger to your org` (appsfolio), `say why the upload failed instead of silently resetting` (refractions).
- The body explains **why** and what was ruled out. End with the session trailer (`Claude-Session: …`) when an agent wrote it.
- Version bumps get their own commit: `Bump version to X.Y.Z`.

## CLAUDE.md — short, directive, pointing outward

Keep it under ~150 lines. It's loaded every session; long files get skimmed. Template: `assets/skeleton/CLAUDE.md`. Sections:

1. **Shape** — the qualifying answers (tenant? SSO? GxP? billing? API?) so the `django-app` skill in Extend mode knows which modules apply.
2. **Commands** — `just setup`, `just dev`, `just test`, `just check`. "Always `uv run`; never bare `pytest`/`python`."
3. **Rules** — the invariants, each one line, imperative. Examples from the repos:
   - "All new tenant-scoped models inherit `TenantIsolatedModel`. **Inheriting the base does not create the policy — the migration does.**"
   - "Reach for `.using("admin")` only where there is genuinely no tenant context — never to 'make a query work'."
   - "A literal product name outside settings defaults is a bug."
   - "Postgres for everything — NO Redis."
   - "Every signature gets a fresh ceremony — never add a session-window skip." (GxP)
4. **Where things are** — `docs/ARCHITECTURE.md` is the authoritative spec (§-numbered, cited from code as "ARCHITECTURE §4"); "Read docs/DEPLOYMENT.md before deploying or releasing anything."
5. **Things that mislead** — hard-won gotchas that look wrong but aren't (refractions). E.g. "CI gates on `ruff check` only, so `ruff format` drift is not a failure."

**Keep it true.** Three of five repos had stale CLAUDE.md facts (Python version, user model path, Gunicorn vs uvicorn, Swarm vs Compose). When a change invalidates a CLAUDE.md line, fix the line in the same commit. Version numbers belong in `pyproject.toml`, not in CLAUDE.md.

## Planning and tracking docs

| File | Holds | Owner |
|---|---|---|
| `docs/PLAN.md` / `docs/<FEATURE>_PLAN.md` | design, phases, key decisions & rationale, open questions | agent + human |
| `TODO.md` | code work an agent can do: "Recently completed ✅" at top, P0 by area, `──── Post-launch (P1+) ────` divider. Remove an entry when it lands. | agent |
| `LAUNCH.md` | work *outside the repo* only a human can do (DNS, SES production access, Stripe live mode, Apple/Google accounts), marked 🔴 hard / 🟡 soft / 🟢 post-launch / ✅, linking runbooks | human |
| `docs/CHANGELOG.md` or `help/changelog.md` | customer-facing, one entry per prod release | agent |

Incident-driven work gets a plan named for it (`PLAN_RLS_SECURITY.md`): threat table, affected counts, phased rollout with gates ("never flip the role before P0+P1 ship").

## docs/ layout

Flat, `UPPER_SNAKE.md`: `ARCHITECTURE.md` (spec), `DEPLOYMENT.md` (with an "Invariants that have bitten us" section), `SECURITY.md`, `TESTING.md`, `STRIPE.md`, `SSO_TESTING.md`, `LEARNINGS.md`, feature `*_PLAN.md`. Business docs (PRICING, MARKETING) may live here or in `marketing/`. `docs/README.md` is a reader's guide by audience. Root `README.md` is short: what it is, quick start, pointer to docs.

User-facing help is **not** in `docs/` — it's `help/` (frontend.md § help).

## QA testbench

For releases touching auth, tenant isolation, billing or permissions, keep a structured manual/agent test plan (meetingsignals `*-testbench.json`):

```json
{"sections": [{"code": "SMK", "name": "Smoke", "note": "Run first against the deployed env. If any case fails, stop and report.",
  "cases": [{"key": "SMK-01", "title": "…", "priority": "P0", "release_focus": true,
             "setup": "…", "steps": ["…"], "expected": "…"}]}]}
```

An agent with a browser tool (agent-browser / playwright-cli) can execute it against test.

## .gitignore

Every ignore has a comment saying why (`assets/skeleton/dot-gitignore`). Must include: `.env` and `.env.*` with `!.env.example`; `*.key`, `*.pem`, `certs/`; `staticfiles/`, `help_site/`, `static/css/output.css`, `bin/tailwindcss`; `db_data/`, `*.sql` dumps; `.claude/settings.local.json` (other `.claude/` files stay tracked); Office lock files `~$*`.

Secrets on disk: fine when gitignored, but never copy prod data dumps (`db_data/devdb.sql`) into the repo tree — use a path outside it.

## Pre-commit

`assets/skeleton/dot-pre-commit-config.yaml`: pre-commit-hooks (trailing whitespace, EOF, `check-added-large-files --maxkb=2000`, `check-merge-conflict`, `check-toml`, `detect-private-key`) + ruff + ruff-format. **Don't pass `--select=I, E, F, W, UP` as args** — YAML splits on the spaces and ruff silently runs only isort (appsfolio found this; gxpsign still has it). Put rule selection in `pyproject.toml` and pass only `--fix`.

Repo-specific guard hooks are welcome (appsfolio's AST check that sensitive-model queries filter by tenant, with a baseline file so only new offenders fail).

## Hygiene

- No debug files committed (`tests/test_zzprobe.py`, stray `not a tty` files from failed redirects).
- Generated files are marked as generated at the top and have a `--check` mode that CI runs.
- `.claude/` agents and skills that ship with the repo are tracked; per-user settings aren't.
