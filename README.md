# skill-marketplace

A [Claude Code](https://claude.com/claude-code) plugin marketplace hosting personal skills.

## Available plugins

| Plugin | Description |
| --- | --- |
| [`gxp-review-general`](plugins/gxp-review-general) | Structured Quality / Technical review of any GxP document or record. Classifies findings as Critical / Major / Minor / Observation against FDA, EU, ICH, and Montai SOPs and delivers a Word review report. |
| [`gxp-doc`](plugins/gxp-doc) | Generate, lint, and retrofit GxP controlled documents as native `.docx`. A `python-docx` builder owns the repeating page header, live page-number fields, clause numbering and table styling so documents cannot drift; a companion linter proves conformance against the bundled style guide. |
| [`executive-pptx`](plugins/executive-pptx) | Create or critique executive PowerPoint presentations using a decision-driven structure: conclusion-titles, one-idea-per-slide, the hardest objection answered on-slide. Draws on Pyramid Principle, BLUF, SCQA, action titles, MECE, and pre-mortem objection handling. |
| [`design-md`](plugins/design-md) | Author, extract, and maintain a project-level `DESIGN.md` following the Google [design.md](https://github.com/google-labs-code/design.md) spec. Creates a single source of truth for brand, color tokens, typography, spacing, and components — and wires `CLAUDE.md` to reference it on every design decision. |
| [`uv`](plugins/uv) | Checks whether the [`uv`](https://github.com/astral-sh/uv) Python package manager is installed and installs it if missing, ensuring it's on `PATH`. Used as a prerequisite by other skills that run Python, or when a `pip install` is requested. |
| [`html-app`](plugins/html-app) | Build elaborate, self-contained single-file HTML app artifacts for claude.ai using React, TypeScript, Tailwind CSS v4, and shadcn/ui. Scaffolds a Vite project with 56 pre-installed components, then bundles everything (JS, CSS, assets) into one inlined HTML file. _Adapted from Anthropic's [`web-artifacts-builder`](https://github.com/anthropics/skills) (Apache 2.0), modernized to Node 20+ / Tailwind v4 / React 19._ |
| [`django-app`](plugins/django-app) | Create, extend, or audit Django 6 apps using house conventions. Qualifying questions (tenant-based → django-rls, SSO, GxP, Stripe, API/MCP) select which reference modules load, so unneeded context stays out. Includes a tested project skeleton rendered by `scripts/render.py`: uv + `src/` layout, justfile, portless HTTPS, Procrastinate + DatabaseCache on Postgres, Tailwind standalone + HTMX, GHCR deploys with promote-by-digest. |

## Use it

### 1. Add the marketplace

From inside Claude Code, run:

```
/plugin marketplace add wshayes/skill-marketplace
```

Other supported sources:

```
/plugin marketplace add https://github.com/wshayes/skill-marketplace.git
/plugin marketplace add /absolute/path/to/skill-marketplace      # local checkout
```

### 2. Install a plugin

```
/plugin install gxp-review-general@skill-marketplace
/plugin install gxp-doc@skill-marketplace
/plugin install executive-pptx@skill-marketplace
/plugin install design-md@skill-marketplace
/plugin install uv@skill-marketplace
/plugin install html-app@skill-marketplace
/plugin install django-app@skill-marketplace
/reload-plugins
```

After reload, the skill is available. If a tool description references the skill (e.g. asking for a "GxP review" of a document), Claude will invoke it automatically; you can also call it explicitly with `/gxp-review-general` when supported, or by referencing the skill in a request.

### 3. Use `gxp-review-general`

Hand Claude a GxP document or record and ask for a review. Useful prompt patterns:

- "Run a QA review on the attached SOP draft."
- "Do a pre-approval technical review of this validation protocol."
- "Post-approval audit-style review of this CAPA record — focus on data integrity."

The skill will:

1. Confirm reviewer role (Quality vs. Technical SME), document status (Draft / Final / Post-Approval), and GxP discipline (GMP / GCP / GLP / GVP / GDP / Part 11).
2. Classify the document type and apply the matching checklist.
3. Produce findings tagged **Critical / Major / Minor / Observation** with regulatory citations and Montai SOP references.
4. Render a Word review report from `assets/review-report-template.md`.

See [`plugins/gxp-review-general/skills/gxp-review-general/SKILL.md`](plugins/gxp-review-general/skills/gxp-review-general/SKILL.md) for the full workflow.

### 4. Manage installed plugins

```
/plugin                              # interactive plugin manager (browse / enable / disable / uninstall)
/plugin marketplace update skill-marketplace
/plugin marketplace remove skill-marketplace
```

## Layout

```
.claude-plugin/
  marketplace.json          # marketplace manifest — lists plugins
plugins/
  <plugin-name>/
    .claude-plugin/
      plugin.json           # plugin manifest
    skills/<skill-name>/
      SKILL.md              # skill entry point (frontmatter + workflow)
      references/           # supporting reference docs the skill loads on demand
      assets/               # templates / artifacts the skill renders
```

## Adding a new plugin

1. Create `plugins/<name>/.claude-plugin/plugin.json` with `name`, `description`, `version`, `author`.
2. Drop the skill into `plugins/<name>/skills/<skill-name>/SKILL.md` (with optional `references/` and `assets/`).
3. Add an entry to `.claude-plugin/marketplace.json` under `plugins`, with `source: "./plugins/<name>"`.
4. Commit and push. Subscribers run `/plugin marketplace update skill-marketplace` to pick it up.
