# Prompt-injection protection

Uploaded documents and retrieved passages are **untrusted data**.

## Guarantees

1. Evidence text is wrapped in `<<<UNTRUSTED_DOCUMENT_EVIDENCE>>>` fences before prompt inclusion.
2. System prompts include an injection guard forbidding following evidence instructions.
3. User messages separate trusted operator instructions from request fields.
4. The model has no tool calling surface for filesystem or arbitrary network access.
5. Outbound HTTP is limited to operator-configured LLM/embedding URLs with SSRF checks.
6. Retrieval always filters by `project_id`; a defense assert blocks cross-project leakage.
7. Citation / evidence IDs returned by the model are scrubbed against the server-supplied allowlist.
8. All mutating AI/job/export APIs require authenticated ownership checks server-side.

## Non-goals

- Perfect resistance against all model jailbreaks
- Guaranteeing that model prose never echoes adversarial phrases from documents
