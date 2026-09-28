---
name: gxp-review-general
description: Conduct a structured Quality or Technical review of any GxP document or record, classify findings as Critical/Major/Minor/Observation against FDA, EU, ICH, and applicable Montai SOPs, and deliver a Word report. Use whenever someone asks for a "GxP review", "QA review", "quality review", "technical review", "SME review", "draft review", "pre-approval review", "post-approval review", or "compliance check" on any controlled document (SOP, policy, protocol, plan, specification, method, master record) or GxP record (batch record, log, certificate, training record, deviation, CAPA, change control, audit report, validation report). This is the GENERAL-PURPOSE GxP review skill — use it for Montai-internal docs, vendor docs outside the CMO pre-approval playbooks, drafts being authored, and post-approval retrospective audits.
---

# General GxP Document & Record Review

This skill produces a structured, regulator-defensible review of any GxP document or record. The deliverable is a Word review report with findings classified as **Critical / Major / Minor / Observation** and a status-appropriate disposition.

The skill works for:
- **Either reviewer role** — Quality (QA / QC / Compliance) or Technical (SME — Process, Analytical, Regulatory, Clinical, Data Science, IT, etc.)
- **Any document status** — Early Draft, Final Review (pre-approval), or Post-Approval (retrospective / audit-style)
- **Any GxP discipline** — GMP, GCP, GLP, GDP, GVP, or computerized-system / data-integrity reviews (GAMP 5, 21 CFR Part 11, EU Annex 11)

---

## High-level workflow

1. **Intake** — confirm reviewer role, document status, and GxP discipline (Step 1)
2. **Retrieve** the document from its source (Step 2)
3. **Classify** the document type and load the matching checklist (Step 3)
4. **Frame** the review against reviewer perspective + document status (Step 4)
5. **Review** against the regulatory framework, applicable Montai SOPs, and internal consistency (Step 5)
6. **Draft** findings with severity, location, and regulatory citation (Step 6)
7. **Self-check** every finding against the source text (Step 7)
8. **Render** the Word review report (Step 8)
9. **Hand off** with summary and offer follow-ups (Step 9)
10. change

---

## Step 1 — Intake (the three-question gate)

Before any review begins, the skill needs three pieces of information. If any one is unclear from the request and uploaded materials, **ask the user up front using a single combined `ask_user_input_v0` call** — do not start reviewing.

| Question | Options |
|---|---|
| **Reviewer role** | Quality (QA / QC / Compliance) · Technical / SME · Combined (one person playing both) |
| **Document status** | Early Draft (in authoring) · Final Review (pre-approval / pre-signature) · Post-Approval (retrospective / audit-style) |
| **GxP discipline** | GMP · GCP · GLP · GDP · GVP · GAMP 5 / Part 11 / Annex 11 (computerized systems & data integrity) · Other (ask which) |

Inferring is fine when context is clear:
- "Review my draft of SOP-10" → Quality (it's a controlled doc) · Early Draft · GMP (default for Montai unless the doc indicates otherwise)
- "Tech review on this analytical method validation report before I sign it" → Technical · Final Review · GMP
- "Help me audit our completed clinical site monitoring report" → Quality · Post-Approval · GCP

**Optional follow-up** (ask only if material to the review): regulatory jurisdiction (FDA only / EU only / both / ICH-aligned global default). When unstated, default to **both FDA and EU with ICH harmonization** — Montai's pipeline is U.S.-IND-led but EU expansion is on the horizon.

Once the three answers are in hand, restate them in one line ("Quality reviewer · Final Review · GMP — proceeding") and continue.

---

## Step 2 — Retrieve the document

Choose the tool by source:

- **Box link** (`app.box.com`, `*.box.com`) → `Box:get_file_content` for text extraction; `Box:get_file_preview` for visual inspection of PDFs/images. For folders, `Box:list_folder_content_by_folder_id`.
- **SharePoint link** (`montai.sharepoint.com`) → `Microsoft 365:read_resource` with the file URI; resolve via `Microsoft 365:sharepoint_search` if needed.
- **Uploaded file** at `/mnt/user-data/uploads/` → for `.docx`, run `pandoc --track-changes=all input.docx -o output.md` to capture tracked changes; for complex `.docx` with forms / embedded objects, also unpack via `python /mnt/skills/public/docx/scripts/office/unpack.py` to inspect the underlying XML. For `.pdf`, read `/mnt/skills/public/pdf-reading/SKILL.md` first.
- **Notion / Confluence** → use the corresponding connector.

**Whatever the source, scan for these red flags during retrieval** (they often become findings on their own):
- Unresolved tracked changes
- Open reviewer comments / unresolved queries
- Broken cross-references (`Error! Reference source not found`, `{错误!未找到引用源}`)
- Blank signature blocks or unsigned approval pages
- Placeholder text (`TBD`, `<XX>`, `XXXX`, `[Insert …]`)
- Inconsistent dates between cover page, revision history, and effective date
- Missing or non-current document number in headers/footers

---

## Step 3 — Classify the document type and load the checklist

Read `references/document-type-checklists.md`. It covers:

- Procedural documents — SOP, Policy, Work Instruction
- Plans & Protocols — validation, qualification, stability, study, clinical, analytical method validation
- Reports — validation, qualification, stability, study, audit, deviation, CAPA, change control, technical
- Specifications — drug substance, drug product, raw material, in-process, container/closure
- Master records & batch records — MBR, BPR, MFR, MPR
- Methods — analytical, microbiological, clinical assay, bioanalytical
- Logs & forms — logbooks, training forms, equipment logs, completed forms
- Quality Agreements (QTA / QAA)
- Certificates — CoA, CoC, CoO, Release certificates
- Computerized-system records — validation packages, periodic reviews, audit trails

Each section contains a focused pass/fail checklist. If the document spans types (e.g., a method that includes a validation report), load both checklists.

**Always load** `references/severity-and-regulatory.md` as well — it contains severity definitions, the FDA / EU / ICH / USP / OECD / PIC/S regulatory framework, and how to choose citations.

---

## Step 4 — Frame the review (perspective × status)

Read `references/reviewer-perspectives.md` for the **Quality vs. Technical vs. Combined** focus and `references/status-modulation.md` for how the **document status** changes review depth and severity grading.

The short version:

| | Early Draft | Final Review | Post-Approval |
|---|---|---|---|
| **Quality reviewer focus** | Template / structure conformance, regulatory framework alignment, gap-finding | Full compliance, signatures, traceability, ALCOA+, training linkage, ready-to-sign call | Audit-perspective: change-control / CAPA triggers, deviation linkage, periodic-review readiness |
| **Technical reviewer focus** | Scientific logic, methodology soundness, feasibility, calculations | Verify all technical content; reproducibility; specification linkage | Verify the document still reflects current technical reality; flag stale procedures |
| **Severity bias** | Cap most findings at Major; reserve Critical for fundamental flaws | Full C/M/m/O range applies | Critical findings here typically trigger immediate change control / quarantine — be deliberate |

This framing is captured in the report's "Review Scope" section so the reader knows which lens was applied.

---

## Step 5 — Conduct the review

Apply the loaded checklist in roughly this order:

1. **Approval / signature integrity** — appropriate signatures present (or absent, if early draft); effective dates consistent; revision history matches the cover page; document control metadata complete.
2. **Tracked changes & open comments** — for Final Review, all must be resolved before signature; for Early Draft, summarize what's still open; for Post-Approval, flag any that survived approval (this is a finding).
3. **Internal consistency** — every cross-reference resolves; numerical values agree across sections; figures, tables, and text all tell the same story.
4. **Regulatory alignment** — does the document meet the applicable FDA / EU / ICH / USP / OECD / PIC/S requirements for the GxP discipline? Use `references/severity-and-regulatory.md` for the citation menu.
5. **Montai SOP / Policy alignment** — does the document comply with Montai's own controlled procedures? Use `references/montai-sop-policy-index.md` to identify which Montai POL/SOP/FRM apply, and **fetch them on demand from Box folder `330567208254`** when their content is material to a finding (e.g., a CAPA write-up requires checking SOP-04; a batch release record requires checking SOP-06 and FRM-06-01). Do not bulk-fetch all SOPs at the start of the review — fetch only what's relevant.
6. **Specification / acceptance-criteria traceability** — for methods, BPRs, CoAs, stability documents: do acceptance criteria trace to the registered DS / DP specification? Mismatches are almost always Critical or Major.
7. **Completeness** — required sections present (scope, references, definitions, equipment, materials, procedure, calculations, acceptance criteria, deviations, reporting, revision history, signatures).
8. **Safety & environmental controls** — for documents involving hazardous reagents, radiation, biologic agents, or controlled substances: monitoring, PPE, and waste handling explicit and aligned with site EHS.
9. **Data integrity (ALCOA+)** — Attributable, Legible, Contemporaneous, Original, Accurate, plus Complete, Consistent, Enduring, Available. Especially relevant for batch records, lab notebooks, electronic-system records, and any document that captures GxP data.
10. **Editorial & formatting quality** — typos, unit errors, formula errors. Usually Minor; escalate if the error sits in an operator instruction or a calculation.

---

## Step 6 — Draft findings

Every finding has six required elements:

1. **Finding ID** — `F-{NN}` (e.g., `F-01`, `F-02`) within the report; if the user maintains a Findings Register, propose register-style IDs (e.g., `{DocID}-C01`, `{DocID}-M03`) on hand-off.
2. **Severity** — Critical · Major · Minor · Observation. See `references/severity-and-regulatory.md`.
3. **Title** — one-line declarative summary.
4. **Description** — the issue, written so an author can act on it without seeing the full report. Include the specific value, section number, and what is wrong.
5. **Location** — section or page reference, plus (optional) a verbatim snippet ≤15 words in quotation marks. Hard limit: ≤15 words per snippet. Multiple verbatim snippets across findings are allowed and encouraged where they make the finding directly verifiable against the source — there is no cap on the number of snippets per source.
6. **Reference** — the specific regulatory citation (section level, not just "ICH Q2") **and/or** the specific Montai SOP/Policy clause. Both when both apply.

Order findings: **Critical → Major → Minor → Observation**, then by document section within each severity tier.

---

## Step 7 — Self-check (anti-hallucination gate)

Before rendering the report, re-read the source and verify each finding:

- [ ] The cited section/page actually exists and contains what the finding claims
- [ ] Any quoted snippet is verbatim (and ≤15 words per snippet; multiple snippets per source are allowed)
- [ ] Any numerical claim traces to a specific value or table in the source
- [ ] The regulatory or SOP reference is correct, current, and section-specific

If a finding fails self-check, either correct it against the actual source or remove it. **Better to issue 8 solid findings than 12 where one is fabricated.** A single hallucinated finding damages reviewer credibility and delays approval cycles.

When complete, state in chat: "Self-check complete: N findings verified against source."

---

## Step 8 — Render the Word review report

Use the `docx` skill at `/mnt/skills/public/docx/SKILL.md`. The output skeleton is in `assets/review-report-template.md` — follow it.

Required sections (all):

1. **Cover / title block** — "GxP Review — {Document ID} {Version}"
2. **Reviewer block** — Reviewer name, role (Quality / Technical / Combined), review date
3. **Document metadata table** — Document ID, Title, Version, Effective/Issue date, Status (Draft / Final Review / Post-Approval), Originator, Owner, GxP discipline
4. **Review scope** — one paragraph stating the perspective × status framing from Step 4
5. **Severity definitions table** — from `references/severity-and-regulatory.md`
6. **Findings summary** — counts by severity with a one-line disposition
7. **Detailed findings** — grouped by severity, then by document section. Each finding rendered as a sub-heading + a small table of ID / Severity / Title / Description / Location / Reference
8. **Author / Owner query table** (if any Major or Critical) — one row per item, phrased as a clear, actionable question
9. **Disposition / recommendation** — status-appropriate language (see Step 8a below)
10. **Regulatory & internal references cited** — full list of every citation used in the findings

### Step 8a — Status-appropriate disposition language

| Status | Disposition options |
|---|---|
| Early Draft | Continue authoring with revisions · Substantive rework required · Restructure (template / approach mismatch) |
| Final Review | Approve as written · Approve with editorial revisions · Conditional approval pending Major resolution · HOLD — do not approve (Critical or unresolved Major) · Reject |
| Post-Approval | No action required · Initiate change control to address findings · CAPA required (per SOP-04) · Supersede / revise document · Withdraw document |

Pick exactly one. The disposition should follow automatically from the findings — a single unresolved Critical at Final Review = HOLD; multiple unresolved Majors = HOLD or Conditional.

**File naming**: `{DocID}_GxP-Review_{YYYYMMDD}.docx`, saved to `/mnt/user-data/outputs/`. If the document has no ID, use a slugged version of the title.

---

## Step 9 — Hand off

Use `present_files` to deliver the Word report. In chat, include only:

- One-paragraph executive summary (counts + disposition + the single most important finding)
- Bullets for each Critical and the top 2–3 Major
- Explicit disposition
- Offer next steps based on status:
  - Early Draft → offer to draft a revised version of the most-impacted sections
  - Final Review → offer to draft a query letter / response template for the author
  - Post-Approval → offer to draft a Change Control or CAPA initiation memo (referencing SOP-04 if CAPA)

Do **not** restate the full report in chat. The Word file is the deliverable.

---

## Conventions and house style

- **Tone** — professional, direct, neutral. Findings state facts; the recommendation states what is needed. No advocacy.
- **Voice** — third person. "The review identified…" / "The document does not…" — not "I found…".
- **Quoted text** — in quotation marks with section/page reference. Hard limit: ≤15 words per quote. Use verbatim quotes wherever they make a finding directly verifiable against the source; there is no per-source cap on the number of quotes.
- **People** — full names on first reference. If signing roles aren't named in the document, use placeholders like "Document Owner" / "QA Approver" rather than guessing.
- **Compounds** — full code on first reference (e.g., `MR-0033809`, `MTAI-1025`); afterward, the short form is fine.
- **Dates** — ISO format (`2026-04-28`) or `28 Apr 2026`; never US-style numeric (`04/28/2026`) in regulatory text — it's ambiguous to non-US readers.

---

## Output quality bar

A review is acceptable for delivery when:

- [ ] The three-question intake is reflected in the report's Review Scope section
- [ ] Every finding traces to a specific, quotable location in the source
- [ ] Severity grading is reproducible: another reviewer applying the same definitions would classify each finding the same way ±1 level
- [ ] Disposition follows automatically from findings (no Critical → not HOLD)
- [ ] Regulatory citations are section-specific (not "ICH Q2" but "ICH Q2(R2) §5.5")
- [ ] Montai SOP citations are clause-specific when the SOP was the basis for a finding
- [ ] The Word report is at `/mnt/user-data/outputs/` and was delivered via `present_files`
