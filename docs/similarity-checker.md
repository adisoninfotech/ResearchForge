# Similarity and citation-risk checker

ResearchForge provides an **advisory** textual-overlap and citation-risk review. It does **not** guarantee originality.

## Required product language

Use:

> No significant textual overlap was identified within the sources checked.

Never state:

- Zero plagiarism
- Plagiarism-free guarantee
- Guaranteed originality
- Equivalent to Turnitin or iThenticate

Every report requires human review (see report footer disclaimer).

## Coverage (initial)

Checked when available:

- Uploaded reference documents (extracted text)
- Other documents in the same project
- User-authorized prior manuscripts (explicit project IDs)
- Optional administrator-provided open-license corpus snippets

Not checked by default:

- Subscription-only publisher full-text databases (not scraped or copied)
- Licensed commercial providers unless a real adapter is configured (`similarity_licensed_provider=null` by default)

## Ensemble methods

| Method                   | Role                                  |
| ------------------------ | ------------------------------------- |
| Exact phrase             | Long shared sentence/phrase sequences |
| Word n-gram Jaccard      | Near textual overlap                  |
| Character n-gram Jaccard | Near textual overlap                  |
| MinHash                  | Candidate discovery                   |
| Embeddings               | Semantic similarity                   |
| Reranker                 | Confirmation (identity or configured) |
| Internal duplication     | Same-manuscript section overlap       |
| Self-overlap             | Authorized prior manuscripts          |

Threshold profiles: `default`, `strict` (see API `/similarity/meta`).

**There is no single unexplained overall percentage.**

## Finding classes

Exact/near textual overlap, semantic similarity, proper quotation, properly cited paraphrase, citation potentially required, excessive similarity despite citation, common technical phrase, bibliography/title match, self-overlap, internal duplication, needs human review.

A citation does **not** automatically make extensive copying acceptable.

## Rewrite workflow

Proposed rewrites must preserve meaning and cite where needed. They must **not** aim to evade detection. Acceptance is required; the relevant check is re-run afterward.
