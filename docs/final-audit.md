# Final product-behavior audit (private beta)

**Auditor role:** Independent principal engineer  
**Date:** 2026-08-02  
**Scope:** Full monorepo vs 24 required product behaviors  
**Method:** Code inspection, gap analysis, implementation fixes, new tests, full validation suite

---

## Fixed issues (this audit)

| #     | Issue                                        | Fix                                                                                           |
| ----- | -------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 2     | Guest copy overstated “browser only”         | Clarified `GUEST_STORAGE_MESSAGE` (outline metadata may reach AI; draft not a server project) |
| 3–4   | Incomplete unauth gate coverage              | Added integration matrix for projects/files/exports/similarity/AI                             |
| 5     | Optional conversion key / race               | `guest_conversion_key` required; IntegrityError → idempotent return                           |
| 7     | Offline 409 could retry silently             | Offline flush drops 409 items and surfaces conflict UI                                        |
| 7     | Malformed `If-Match` silently ignored        | Returns 400 validation error                                                                  |
| 8     | Restore left orphan sections                 | Sections absent from snapshot are cleared to empty                                            |
| 9     | Retention enums weakly applied               | `trash_30` / `inactive_draft_90` now drive timers                                             |
| 9     | Engagement `delete_now` skipped confirmation | Requires `confirmation: "DELETE"` + UI prompt                                                 |
| 10    | Restore always → ACTIVE                      | Persists `status_before_trash` and restores prior status                                      |
| 11    | Deletion notices re-sent hourly              | `deletion_notice_sent_at` dedupe (migration `20260802_0010`)                                  |
| 12    | Purge deleted DB when storage failed         | Abort DB delete if `delete_prefix` fails; paginate S3 listing                                 |
| 15–16 | Expand with empty evidence                   | Server rejects `expand_with_evidence` without evidence; draft gets hard constraint            |
| 15    | Client-trusted chunk text                    | `chunk_id` resolved from DB under `project_id` only                                           |
| 17    | Simulated labels unlockable                  | `SIMULATED_EXPERIMENT` sets `label_locked`                                                    |
| 19    | Weak download footer coverage text           | Footer includes full limitations list + clearer summary                                       |
| 21    | Export returned raw `storage_url`            | Removed; authenticated token path only; single-use tokens                                     |
| 22–24 | Thin isolation tests                         | Intruder matrix + same-owner cross-project chunk rejection tests                              |

---

## Verified behaviors (with evidence)

### 1. Guests can try limited features — **Verified**

- UI: `apps/web/src/components/guest-workspace.tsx`
- API: `POST /api/v1/guest/outline` (`apps/api/app/api/v1/guest.py`)
- Caps: `guest_outline_max_sections`; gated actions listed in schemas/shared-types
- Tests: `test_guest_outline.py`, Playwright smoke

### 2. Guest content stored only in the browser — **Verified (with disclosure)**

- Client: `apps/web/src/lib/guest-storage.ts` → localStorage only
- No guest manuscript/project rows created by outline endpoint
- Copy now discloses AI outline metadata transit

### 3. Guests cannot save server-side — **Verified**

- `CurrentUser` on project/manuscript writes
- Tests: `test_guest_cannot_save_project_apis`, `test_guest_cannot_access_gated_server_apis`

### 4. Save / permanent upload / full export / full similarity require login — **Verified**

- Server: `files.py`, `exports.py`, `similarity.py`, `manuscripts.py`, `ai.py` all require auth
- UI gates + new unauth matrix test

### 5. Guest drafts transfer safely after auth — **Verified (hardened)**

- `convert_guest_draft` idempotent on `(owner_id, guest_conversion_key)`
- Key required; race handled
- Tests: `test_guest_conversion_idempotency`, e2e auth-guest-flow

### 6. Logged-in users receive autosave — **Verified**

- `useAutosave` + `PUT .../sections/{id}`
- Test: `test_logged_in_user_can_create_and_autosave`

### 7. Autosave cannot silently overwrite newer revision — **Verified (hardened)**

- OCC via `expected_revision` → 409
- Offline 409 dropped; overwrite only via explicit UI
- Tests: `test_concurrent_editing_conflict`, concurrent load test

### 8. Version history and restore — **Verified (hardened)**

- `versions.py` list/create/restore/compare + UI `version-history.tsx`
- Restore clears orphan sections
- Test: `test_version_restore_creates_new_version`

### 9. Users can control retention — **Verified (hardened)**

- Policies on create/update; Keep/Archive/Export/Delete now
- Policies now affect trash/inactive timers

### 10. Trash supports recovery — **Verified (hardened)**

- `/trash`, `/restore`, empty trash; prior status restored

### 11. Scheduled deletion warning-based, retry-safe, auditable — **Verified (hardened)**

- Notices + audit `PROJECT_TRASHED` / `PROJECT_PURGED`
- Notice dedupe; storage failure blocks purge (retryable)

### 12. Project deletion removes uploaded/generated objects — **Verified (hardened)**

- `delete_prefix(projects/{id}/)` with pagination; DB delete only after storage OK
- Tests: object deletion + storage-fail abort

### 13. User content private by default — **Verified**

- `is_private=True` on create; ownership 404 isolation
- Note: AI provider receives content when AI used (disclose in privacy policy)

### 14. Training opt-in off by default — **Verified**

- Model/DB/UI/config defaults false; tests cover registration default

### 15. AI grounded in supplied evidence — **Verified (hardened)**

- Facts + fenced evidence; chunk_id server-resolved; expand requires evidence

### 16. No invented citations/results without warnings — **Verified (partial hard guarantees)**

- Prompt prohibitions + citation ID scrub + draft constraint when no evidence
- Fake provider warns; real LLM still prompt-dependent for prose (see deferred)

### 17. Synthetic datasets permanently labeled — **Verified (hardened)**

- Locked labels for synthetic + simulated experiment; API rejects removal

### 18. Result figures require data provenance — **Verified**

- `create_result_figure` requires dataset_version or analysis_run
- Test: `test_provenance_labels_and_conceptual_separation`

### 19. Similarity reports state limited coverage — **Verified (hardened)**

- `COVERAGE_LIMITATIONS`, coverage panel, footer limitations list
- Tests assert safe language

### 20. No zero-plagiarism promise — **Verified**

- Forbidden claims / safe summary constants; UI + API meta; tests

### 21. Downloads authenticated and short-lived — **Verified (hardened)**

- Export grants: auth + TTL + single-use; no `storage_url`
- File downloads: ownership-gated signed URLs (capability after mint — see deferred)

### 22. Project-level authorization everywhere — **Verified**

- `get_owned_project` on project-scoped routes (inventory in prior audit)
- Intruder matrix test added

### 23. Uploaded documents untrusted — **Verified**

- Magic-byte/zip safety/quarantine; evidence fenced in prompts; injection guard
- Tests: zip safety, prompt fencing

### 24. Tests prevent cross-user/cross-project leakage — **Verified (expanded)**

- Existing isolation tests + new `test_audit_isolation.py` (intruder matrix, cross-project chunk, download single-use)

---

## Remaining launch blockers

1. **Real email provider** (not console/fake) for verification, reset, deletion notices
2. **Real malware scanner** (`malware_scanner` still `fake`/`none`)
3. **Published Privacy / Terms / AI / similarity / retention disclosures** (legal pages are thin)
4. **Backup verification + restore drill** in production environment
5. **Support / abuse / incident response contacts** live
6. **Production secrets** (no `dev-only-*`); TLS + CORS for beta domain
7. **Billing** disabled or fully configured

---

## Deferred enhancements

| Item                                                                | Why deferred                                          |
| ------------------------------------------------------------------- | ----------------------------------------------------- |
| Deterministic prose citation/metric scrubbing for real LLMs         | Needs NLP heuristics + product UX for blocked accepts |
| Server-auto-attach pinned evidence (not only paste/`chunk_id`)      | Product UX for evidence picker                        |
| File downloads as single-use session tokens (vs S3 capability URLs) | Broader client change                                 |
| Central `OwnedProject` FastAPI dependency                           | Refactor hygiene, not a current hole                  |
| Dense autosave version snapshots                                    | Product tradeoff (storage vs history)                 |
| HTML→TipTap parse on guest convert                                  | Fidelity polish                                       |
| Draft-scheduled-deletion preference emission                        | Prefs exist; wire email path                          |
| OpenTelemetry exporter                                              | Observability hooks exist; export wiring ops          |

---

## Manual checks that cannot be automated

1. Visual review of guest ↔ auth dialogs on mobile/desktop
2. Two-browser-tab conflict UX (Accept server / Overwrite) with a human
3. Real vLLM/model run: adversarial document (“ignore system prompt”) does not change tools (no tools exist) and warnings appear
4. Production S3 SSE / disk encryption confirmation with cloud console
5. Legal counsel sign-off on Privacy/Terms/AI disclosure language
6. GPU/vLLM license review for chosen weights
7. Restore drill from encrypted backup onto staging
8. Abuse mailbox triage dry-run

---

## Migration note

- Alembic head after this audit: **`20260802_0010`** (`status_before_trash`, `deletion_notice_sent_at`)

---

## Validation results (this audit)

| Suite                     | Result                                |
| ------------------------- | ------------------------------------- |
| API ruff + mypy           | clean                                 |
| API pytest                | **107 passed**                        |
| Prettier format check     | clean                                 |
| Web typecheck             | clean                                 |
| Web vitest                | **8 passed**                          |
| Next.js production build  | success                               |
| Playwright                | **2 passed**                          |
| Alembic head              | `20260802_0010` (10 revisions)        |
| Docker / empty-DB migrate | CI-covered (Docker not on audit host) |

```bash
# API
cd apps/api && ruff check app tests && ruff format --check app tests && mypy app
pytest -q

# Web
npm run format:check && npm run lint --workspace=@researchforge/web
npm run typecheck --workspace=@researchforge/web
npm run test --workspace=@researchforge/web
npm run build --workspace=@researchforge/web
npm run test:e2e --workspace=@researchforge/web
```
