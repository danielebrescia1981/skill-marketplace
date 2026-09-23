# GxP — 21 CFR Part 11 / EU Annex 11 / GAMP 5

**Load:** only when Q3 = yes. Reference implementations: gxpsign (e-signatures), eqms (QMS). Controlled documents (URS, RA, VP, SOPs) are written with the **`gxp-doc`** skill, and reviewed with `gxp-review-general`.

GxP changes *how* you build and release, not just what. Settle these before the first feature.

## Data integrity (ALCOA+) in the model layer

- **Audit trail, two layers:**
  1. `django-simple-history` (`HistoricalRecords()` + `HistoryRequestMiddleware`) on every GxP-relevant model. It answers who changed what and when. With tenancy, the `Historical*` tables need RLS policies too (tenancy-rls.md).
  2. **Append-only event logs** for signatures and other regulated events. They can't be edited or deleted through the ORM:
     ```python
     class SignatureAuditLog(TenantIsolatedModel):
         id = models.UUIDField(primary_key=True, db_default=UUIDv7(), editable=False)
         def save(self, *a, **kw):
             if not self._state.adding:
                 raise AuditRecordImmutable("Audit records are immutable. Record a correcting entry instead.")
             super().save(*a, **kw)
         def delete(self, *a, **kw):
             raise AuditRecordImmutable("Audit records cannot be deleted.")
     ```
     Pair it with a QuerySet whose `update()`/`delete()` raise, so bulk paths are blocked too.
- **Tamper evidence (eqms `signatures/hashchain.py`):** `entry_hash = SHA-256(chain_version ‖ prev_hash ‖ canonical_payload)`. One chain per tenant per log, serialised with `SELECT … FOR UPDATE` on a `HashChainHead` row, and versioned canonicalisation. `manage.py verify_audit_chain` re-walks it. Mark the global lock with a `ponytail:` comment naming its throughput ceiling.
- **Admin actions** audited separately (gxpsign `AdminActionAuditLog`): hooks on `ModelAdmin`, secrets redacted by field name, *not* tenant-isolated, tenant stored as a value rather than an FK so the record outlives the tenant.
- Record `ip`, `user_agent`, `authenticator_method`, and for WebAuthn the credential id, aaguid, `user_verified` and `sign_count`.
- Files: store a SHA-256 at upload and re-verify it on every download. `AWS_QUERYSTRING_AUTH = False` makes all downloads go through the app.
- Time: UTC in the DB, shown in the user's zone with the offset. Server time comes from NTP (an IQ check).
- Comments cite the requirement: `# URS-AUD-06b`, `# Annex 11 §13.3`, `# 21 CFR 11.10(e)`.

## Electronic signatures

- **Signature meanings are first-class** (`signatures/meanings.py`): authored, reviewed, approved, and so on, each with a minimum authenticator strength (e.g. *approved* requires MFA or a passkey). The meaning is frozen onto the request when it's sent.
- **A fresh re-authentication ceremony for every signature** (`tenants/gxp_reauth.py`) via WebAuthn, password, or SSO step-up. Never add a session-window skip ("signed in the last 5 minutes") — Annex 11 §13.3 and Part 11 §11.200. Put that rule in CLAUDE.md.
- Signature tokens are single-use. Segregation-of-duties checks (`people/sod.py`) stop the author approving their own record.
- Signed PDFs: pyHanko PAdES B-B with a platform certificate (`certs/`, gitignored, imported by a management command, pushed to servers by `just cert-push`). Stamp signer, meaning and time visibly, and record the same in the audit log.
- Sessions: an idle timeout per tenant (`SessionInactivityTimeoutMiddleware`). Session length can be long *because* every signature re-authenticates.

## Validation (CSV / CSA) wired into the repo

- **Requirements** live in `gxp_spec_files/` (URS, FS, DS, IS as Markdown with IDs like `URS-ACC-01`, `FS-108`), or as generated controlled `.docx` from `tools/qms/build_*.py` via `gxp-doc`. Rule: "Edit the script, not the .docx."
- **Tests trace to requirements** with **pytest-gxp**:
  ```python
  @pytest.mark.gxp
  @pytest.mark.requirements(["FS-108"])
  @pytest.mark.traces_to("URS-ACC-01")
  @pytest.mark.gxp_risk("medium")
  def test_approval_requires_fresh_reauth(...): ...
  ```
  `pytest --gxp` writes `gxp_report_files/`: validation report (md/json/csv/pdf), `traceability_matrix.*`, `requirement_coverage.md`, `evidence/` screenshots, `artifact_manifest.sha256`.
- **Pin the validation tool exactly**: `pytest-gxp==0.3.0` with the comment "Changing this version requires re-qualification."
- **Gaps can't go stale:** `gxp_gap_report.md` lists uncovered requirements, and `tests/test_qualification.py` fails if the list is wrong in *either* direction. `build_rtm.py --check` exits non-zero on a gap.
- **`validation/`** is a standalone pytest suite (`pytest -c validation/pytest.ini`) that **must not import the Django app**. It tests the *deployed* system over HTTPS, SSH and docker:
  - `iq_test/`, `iq_prod/`: installation qualification (image digest, env, TLS, backups configured, NTP, DB roles).
  - `oq_test/`, `oq_prod/`: operational qualification, some scripted and some scripted-manual with execution records.
  - It refuses to run unless the deployed `APP_ENVIRONMENT` matches the target, and an unreachable target *skips*, never passes.
  - Phase order: IQ test → OQ test → IQ prod → OQ prod subset. PQ belongs to the customer; ship them a PQ template.
  - `validation/justfile` *is* the procedure (`dry-run, precheck, iq-test, oq-test, iq-prod, oq-prod, verify-report, freeze`). `CHECKLIST.md` is a reading copy.
- **Per-release qualification delta**: a `qualification/baseline_<ver>.json` hashes each requirement's tests, and `manage.py qualification_delta` prints the re-test subset for the customer's change control (eqms).

## Release and change control

- **One build per release**: prod promotes the digest that ran on test and is never rebuilt, never `:latest` (devops.md § Promote by digest, gxpsign `workflow-deploy-prod.yml`). The prod workflow's `qualify` job produces the evidence chain *commit on main = commit built for test = digest running on test* before anything changes.
- `docs/CHANGELOG.md`: each release has `### Validation Impact: None|Low|Medium|High` and a table with "21 CFR Part 11" and "GAMP5 Category" columns.
- GitHub as part of the validated toolchain: document what a PR approval *is* and *isn't* ("PR approve ≠ Part 11 signature") in `docs_validation_info/GITHUB-AS-VALIDATION-SYSTEM.md`.
- Release authorisation happens in the QMS, outside GitHub. The `production` environment exists for deployment history, not as an approval gate.
- Backups with a stated RPO (`backup-<app>-prod.sh`: daily `pg_dump | gzip`, fail if the dump is under 1 KB, 14-day retention, comment citing `URS-PER-07 (RPO ≤ 24h)`), and a restore test is part of IQ.

## Where controlled documents live

Controlled documents (validation plan, URS, RA, VSR, SOPs, training records) live in the QMS / Drive, not in git. They may be symlinked into the repo (`docs_validation → Drive`) for the generator scripts, but the symlinks are gitignored. The repo holds only generators, test evidence and the traceability they're built from.

## Security posture GxP adds

On top of security.md: `SECURITY_HARDENING` on in test *and* prod; CSP enforced, not report-only; password minimum 12 plus complexity; API token TTL; `check --deploy` clean as an OQ test; data residency system check if promised.
