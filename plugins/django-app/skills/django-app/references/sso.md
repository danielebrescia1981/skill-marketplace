# SSO

**Load:** only when Q2 ≠ none. Read only the section for the chosen kind.

| Kind | Who configures the IdP | Library | Requires |
|---|---|---|---|
| **A. Per-tenant enterprise SSO** (OIDC/SAML, e.g. Entra ID, Okta, Google Workspace) | each customer org's admin, in-app | **damsso** (house library) | tenancy-rls.md |
| **B. Social login** ("Sign in with Google/Microsoft") | you, once, in settings | allauth `socialaccount` | nothing |

Both sit on top of the allauth email baseline (foundation.md § Auth). A user who never uses SSO still works.

---

## A. Per-tenant SSO with damsso

Used by appsfolio, eqms, gxpsign. Pin it: `damsso = { git = "https://github.com/wshayes/damsso", tag = "vX.Y.Z" }` (check the latest tag).

### Wiring

```python
INSTALLED_APPS += ["damsso"]
# tenants/models.py
class Tenant(TenantSSOMixin, models.Model): ...        # adds sso_enabled, sso_enforced, is_active

DAMSSO_TENANT_MODEL = "tenants.Tenant"
DAMSSO_TENANT_SLUG_FIELD = "slug"                      # the slug PK (appsfolio uses "id")
DAMSSO_ENABLE_RLS = False                              # our policies cover tenancy; don't double up
DAMSSO_USE_BUILTIN_INVITATIONS = False                 # when the app has its own invitations
DAMSSO_SSO_USER_POLICY = "tenants.sso_hooks.assert_sso_user_allowed"   # NOT optional — see below
DAMSSO_POST_SSO_USER   = "tenants.sso_hooks.post_sso_user"
FERNET_KEYS = env.list("FERNET_KEYS")                  # encrypts IdP client secrets at rest; list = rotation
# urls.py
path("sso/", include("damsso.urls")),                  # add "/sso/" to TENANT_EXEMPT_PATHS
```

With a slug-PK Tenant, damsso's bundled migrations (which assume a UUID PK) can't migrate a fresh DB. eqms/gxpsign ship an override: `MIGRATION_MODULES = {"damsso": "config.damsso_migrations"}` recreates damsso's schema in its final form, name-compatible with stock damsso. Copy theirs.

### The policy hook is the security boundary

damsso's default JIT provisioning is an email-keyed `get_or_create`: whoever the IdP asserts becomes a local user **with membership in that tenant**. The policy hook turns that into "existing members or invitees only":

```python
def assert_sso_user_allowed(request, tenant, email, userinfo):
    """Raise ValueError (user-safe message) to deny."""
    if User.objects.filter(email__iexact=email, tenant=tenant).exists():
        return
    if Invitation.objects.filter(tenant=tenant, email__iexact=email, accepted=False,
                                 expires_at__gt=timezone.now()).exists():   # your invitation model
        return
    raise ValueError("Your account is not authorized for this organization. Ask an administrator for an invitation.")

def post_sso_user(request, user, tenant, sso_provider):
    if user.tenant_id != tenant.pk:
        user.tenant_id = tenant.pk
    if user.password == "":            # damsso-created users have "", which Django treats as *usable*
        user.set_unusable_password()
    user.save()
    EmailAddress.objects.update_or_create(user=user, email=user.email,
                                          defaults={"verified": True, "primary": True})
```

### Enforcement is in the account adapter

An org uses SSO *or* local passwords, never both. The login page's SSO button is a hint, not a control. Enforce in `AccountAdapter.pre_authenticate`:

```python
def pre_authenticate(self, request, **credentials):
    tenant = self._tenant_for_login(credentials.get("email", ""))
    if tenant and tenant.sso_enabled:
        request.session["sso_tenant_slug"] = tenant.pk      # login page offers the SSO link
        if tenant.sso_enforced:
            # Must RAISE: allauth discards pre_authenticate's return value.
            raise ValidationError("Your organization signs in with SSO.")
    return super().pre_authenticate(request, **credentials)
```

`_tenant_for_login` looks at the known user's own tenant first, then the org claiming the email domain. **Fail closed when more than one org claims the domain** (appsfolio: "lookalike email domains could auto-join a stranger to your org").

### Per-tenant auth policy (optional, GxP-leaning)

eqms puts these on Tenant: `allow_password`, `allow_passkey`, `session_inactivity_timeout_minutes` (enforced by a `SessionInactivityTimeoutMiddleware`), and a minimum authenticator strength. Passkeys use the `webauthn` library with `WEBAUTHN_RP_ID = BASE_DOMAIN_NAME` and `WEBAUTHN_ORIGINS` derived from it. Add these when a customer asks, not before.

### Testing

`docs/SSO_TESTING.md` holds the manual recipe for each IdP (Entra, Okta, Google). Unit tests cover the policy hook (member ✓, invitee ✓, stranger ✗, second org claiming the domain ✗) and adapter enforcement (password login to an enforced org raises).

---

## B. Social login (allauth socialaccount)

```python
INSTALLED_APPS += ["allauth.socialaccount", "allauth.socialaccount.providers.google",
                   "allauth.socialaccount.providers.microsoft"]
SOCIALACCOUNT_PROVIDERS = {
    "google": {"APPS": [{"client_id": env("GOOGLE_CLIENT_ID"), "secret": env("GOOGLE_CLIENT_SECRET")}],
               "SCOPE": ["openid", "email", "profile"], "AUTH_PARAMS": {"prompt": "select_account"}},
    "microsoft": {"APPS": [{"client_id": env("MS_CLIENT_ID"), "secret": env("MS_CLIENT_SECRET"),
                            "settings": {"tenant": "organizations"}}]},
}
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True             # link to an existing account by verified email…
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_ADAPTER = "accounts.adapters.SocialAccountAdapter"
```

…but only when the provider says the email is verified. In the social adapter, reject or force verification when `sociallogin.email_addresses` has none marked verified. Otherwise an attacker can register the victim's address at a lax provider and take over the account.

Keep client secrets in env, not in `SocialApp` DB rows. Env-configured `APPS` is enough, and it keeps secrets out of DB dumps.

---

## Both kinds

- `ACCOUNT_LOGOUT_ON_GET = False`. SSO logout is a POST too.
- `SESSION_COOKIE_SAMESITE = "Lax"`, not Strict: the IdP callback is a cross-site top-level navigation and would arrive without the session cookie.
- An MFA requirement for password users (allauth.mfa) is independent of SSO. Enable it for admin roles at minimum when the data is sensitive.
