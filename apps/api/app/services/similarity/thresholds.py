"""Configurable similarity thresholds — documented profiles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThresholdProfile:
    name: str
    exact_phrase_min_words: int
    word_ngram_n: int
    word_ngram_min_jaccard: float
    char_ngram_n: int
    char_ngram_min_jaccard: float
    minhash_threshold: float
    embedding_min_cosine: float
    rerank_min_score: float
    short_phrase_max_words: int
    common_phrase_min_corpus_hits: int
    excessive_cited_overlap_ratio: float
    paraphrase_word_jaccard: float


PROFILES: dict[str, ThresholdProfile] = {
    "default": ThresholdProfile(
        name="default",
        exact_phrase_min_words=8,
        word_ngram_n=5,
        word_ngram_min_jaccard=0.55,
        char_ngram_n=10,
        char_ngram_min_jaccard=0.45,
        minhash_threshold=0.4,
        embedding_min_cosine=0.82,
        rerank_min_score=0.55,
        short_phrase_max_words=4,
        common_phrase_min_corpus_hits=3,
        excessive_cited_overlap_ratio=0.7,
        paraphrase_word_jaccard=0.35,
    ),
    "strict": ThresholdProfile(
        name="strict",
        exact_phrase_min_words=6,
        word_ngram_n=4,
        word_ngram_min_jaccard=0.45,
        char_ngram_n=8,
        char_ngram_min_jaccard=0.35,
        minhash_threshold=0.3,
        embedding_min_cosine=0.75,
        rerank_min_score=0.45,
        short_phrase_max_words=3,
        common_phrase_min_corpus_hits=2,
        excessive_cited_overlap_ratio=0.55,
        paraphrase_word_jaccard=0.28,
    ),
}


def get_profile(name: str | None) -> ThresholdProfile:
    return PROFILES.get(name or "default", PROFILES["default"])


ALGORITHM_VERSIONS = {
    "exact_phrase": "v1",
    "word_ngram": "v1",
    "char_ngram": "v1",
    "minhash": "v1",
    "embedding": "v1-fake-or-configured",
    "reranker": "v1-identity-or-configured",
    "classifier": "v1",
}


COVERAGE_LIMITATIONS = [
    "Subscription-only publisher databases are not scraped or copied.",
    "Coverage is limited to uploaded references, same-project documents, "
    "user-authorized prior manuscripts, and an optional open-license corpus.",
    "Licensed commercial providers are optional adapters and are not claimed as active coverage.",
    "Semantic similarity can flag related wording that is not copying; human review is required.",
    "A single overall percentage is intentionally not used as a sole risk score.",
]
