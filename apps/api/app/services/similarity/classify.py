"""Citation-aware classification of raw matches."""

from __future__ import annotations

from app.models.enums import SimilarityFindingClass
from app.services.similarity.engine import RawMatch
from app.services.similarity.thresholds import ThresholdProfile


def classify_match(
    match: RawMatch, profile: ThresholdProfile
) -> tuple[SimilarityFindingClass, str, str]:
    """Return (classification, recommended_action, explanation)."""
    exact = match.scores.get("exact", 0.0) >= 1.0 or "exact_phrase" in match.methods
    near = match.scores.get("word_ngram_jaccard", 0.0) >= profile.word_ngram_min_jaccard
    semantic = match.scores.get("embedding_cosine", 0.0) >= profile.embedding_min_cosine
    overlap_ratio = max(
        match.scores.get("exact", 0.0),
        match.scores.get("word_ngram_jaccard", 0.0),
        match.scores.get("char_ngram_jaccard", 0.0),
    )

    if match.is_bibliography or match.is_title_like:
        return (
            SimilarityFindingClass.BIBLIOGRAPHY_OR_TITLE_MATCH,
            "Usually ignore bibliography/title matches unless unexpected.",
            "Match appears to be a bibliography entry or title-like string.",
        )
    if match.is_common or len(match.manuscript_text.split()) <= profile.short_phrase_max_words:
        return (
            SimilarityFindingClass.COMMON_TECHNICAL_PHRASE,
            "Accept as legitimate technical language if appropriate.",
            "Short or common technical/academic phrasing.",
        )
    if match.is_internal:
        return (
            SimilarityFindingClass.INTERNAL_DUPLICATION,
            "Consolidate duplicated wording within the manuscript.",
            "Passage duplicates another section in the same manuscript.",
        )
    if match.is_self:
        return (
            SimilarityFindingClass.SELF_OVERLAP,
            "Cite your prior work or rewrite if reuse is unintended.",
            "Overlap with an authorized prior manuscript by the same user.",
        )
    if match.in_quotes and match.citation_present:
        return (
            SimilarityFindingClass.PROPER_QUOTATION,
            "Keep quotation marks and citation; verify accuracy.",
            "Quoted text with a nearby citation marker.",
        )
    if exact and match.citation_present and overlap_ratio >= profile.excessive_cited_overlap_ratio:
        return (
            SimilarityFindingClass.EXCESSIVE_SIMILARITY_DESPITE_CITATION,
            "Rewrite in your own words; a citation alone does not justify extensive copying.",
            "Extensive close overlap remains despite citation presence.",
        )
    if near and match.citation_present and overlap_ratio >= profile.paraphrase_word_jaccard:
        if overlap_ratio >= profile.excessive_cited_overlap_ratio:
            return (
                SimilarityFindingClass.EXCESSIVE_SIMILARITY_DESPITE_CITATION,
                "Rewrite more substantially while retaining the citation.",
                "Cited but overly close paraphrase of the source.",
            )
        return (
            SimilarityFindingClass.PROPERLY_CITED_PARAPHRASE,
            "Verify paraphrase distance; keep citation.",
            "Paraphrase appears cited; still review closeness.",
        )
    if (exact or near) and not match.citation_present:
        if exact:
            return (
                SimilarityFindingClass.EXACT_TEXTUAL_OVERLAP,
                "Add a citation and/or rewrite the passage.",
                "Exact or near-exact textual overlap without a nearby citation.",
            )
        return (
            SimilarityFindingClass.CITATION_POTENTIALLY_REQUIRED,
            "Add a citation or rewrite to express your own understanding.",
            "Uncited paraphrase or near textual overlap with a checked source.",
        )
    if semantic and not exact and not near:
        if match.citation_present:
            return (
                SimilarityFindingClass.PROPERLY_CITED_PARAPHRASE,
                "Confirm the citation covers the idea; rewrite if too close.",
                "Semantic similarity with citation; not necessarily copying.",
            )
        return (
            SimilarityFindingClass.SEMANTIC_SIMILARITY,
            "Review whether citation is needed for the idea.",
            "Semantic similarity without strong n-gram overlap.",
        )
    if exact:
        return (
            SimilarityFindingClass.EXACT_TEXTUAL_OVERLAP,
            "Rewrite and cite the source where appropriate.",
            "Exact textual overlap detected by phrase matching.",
        )
    if near:
        return (
            SimilarityFindingClass.NEAR_TEXTUAL_OVERLAP,
            "Rewrite and consider adding a citation.",
            "Near textual overlap via word/character n-grams.",
        )
    return (
        SimilarityFindingClass.NEEDS_HUMAN_REVIEW,
        "Inspect side-by-side and decide.",
        "Ensemble signals are mixed; human review is required.",
    )
