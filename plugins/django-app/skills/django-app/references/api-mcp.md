# Public API and MCP server

**Load:** only when Q5 = yes.

## Principles

- **The API and MCP tools call the same service layer as the views** (`<app>/api.py` functions). They share auth and schemas "so the two surfaces cannot drift" (appsfolio `apps/api/mcp.py`).
- One framework. **django-ninja** (pydantic schemas, OpenAPI for free) for new work. eqms uses DRF + drf-spectacular, so match whatever the repo already has.
- Mounted at `/api/v1/`, exempt from session-CSRF and subdomain redirects. Tenant scope comes from the token, never the host.

## Auth

- **Bearer API tokens** as a model: `ApiToken(user, name, token_hash, prefix, created_at, last_used_at, expires_at)`. Store a hash, show the token once, and display the prefix for identification. Default TTL (`API_TOKEN_TTL_DAYS = 90`; Part 11 §11.300(b) wants periodic revision for GxP). Users manage their own tokens at `/app/profile/api-token/`.
- Token secrets encrypted at rest when they must be recoverable (`encrypted-text-field` / Fernet); hashed when not. Prefer hashed.
- The auth class resolves token → user → tenant, then **sets the RLS context** (`set_rls_tenant(user.tenant_id)`) inside the request's transaction. The API uses the same isolation guarantee as the UI.
- Role checks apply unchanged: a Reader token is read-only. `ReadOnlyRoleMiddleware` covers `/api/` too, and MCP's POST-only transport re-checks the role inside each mutating tool.
- Rate limit per token/tenant using the DB cache. Return `429` with `Retry-After`.

## MCP

- **django-mcpz** (house library) exposes tools over streamable HTTP at `/mcp`, with **OAuth 2.1** (`django_mcpz.oauth`) so assistants like Claude connect without pasting tokens. Discovery documents live under `/.well-known/` (tenant-exempt). The consent page itself is *not* exempt, so a user landing on another tenant's consent URL is canonicalised first.
- Tools are thin wrappers over service functions. Descriptions use `PRODUCT_NAME`, never a literal.
- **Snapshot the tool surface**: `just mcp-surface` writes `validation/mcp_tool_surface.json`, and a test fails when the live surface differs. Tool changes then show up in review (eqms).
- Optionally ship a customer-facing skill in `.claude/skills/<app>/SKILL.md` describing the tools (appsfolio).

## Docs and versioning

- OpenAPI at `/api/v1/docs` (ninja) or drf-spectacular. Mirror it in the help site's "API" page with auth instructions.
- Breaking changes need `/api/v2/`, and v1 keeps running until you announce its removal in the changelog.

## Tests

For each endpoint: no token → 401, a token from tenant B can't see tenant A's object (404, not 403, so existence doesn't leak), a Reader can't mutate, and an expired token → 401.
