"""Ensemble textual/semantic overlap methods (no single misleading score)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.files.embeddings import cosine_similarity, get_embedding_provider
from app.services.similarity.thresholds import ThresholdProfile

WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
CITE_RE = re.compile(
    r"\((?:[A-Z][A-Za-z\-]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z\-]+)?,?\s*)+\d{4}[a-z]?\)"
    r"|\\cite\{[^}]+\}"
    r"|\[\d+(?:\s*[,;\-]\s*\d+)*\]"
)
QUOTE_RE = re.compile(r"[\"“”](.{8,}?)[\"“”]")

# Short / common academic phrases treated as technical language candidates
COMMON_PHRASES = {
    "in this paper",
    "in this work",
    "we propose",
    "experimental results",
    "state of the art",
    "as shown in figure",
    "table of contents",
    "et al",
    "for example",
    "in contrast",
    "on the other hand",
    "future work",
    "related work",
}


@dataclass
class SourceDoc:
    key: str
    label: str
    text: str
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)
    section_id: str | None = None
    project_file_id: str | None = None


@dataclass
class RawMatch:
    manuscript_text: str
    manuscript_start: int
    manuscript_end: int
    source_key: str
    source_text: str
    source_start: int
    source_end: int
    methods: list[str]
    scores: dict[str, float]
    citation_present: bool = False
    citation_keys: list[str] = field(default_factory=list)
    in_quotes: bool = False
    is_bibliography: bool = False
    is_title_like: bool = False
    is_common: bool = False
    is_self: bool = False
    is_internal: bool = False


def tokenize(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


def word_ngrams(tokens: list[str], n: int) -> set[str]:
    if len(tokens) < n:
        return set()
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def char_ngrams(text: str, n: int) -> set[str]:
    cleaned = re.sub(r"\s+", " ", text.lower()).strip()
    if len(cleaned) < n:
        return set()
    return {cleaned[i : i + n] for i in range(len(cleaned) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def minhash_signature(tokens: list[str], *, num_perm: int = 64) -> list[int]:
    """Simple MinHash using sha-based permutations (no external dependency)."""
    if not tokens:
        return [0] * num_perm
    shingles = word_ngrams(tokens, 3) or {" ".join(tokens)}
    sig: list[int] = []
    for i in range(num_perm):
        best = 2**64
        for sh in shingles:
            digest = hashlib.blake2b(f"{i}:{sh}".encode(), digest_size=8).hexdigest()
            best = min(best, int(digest[:16], 16))
        sig.append(best)
    return sig


def minhash_similarity(a: list[int], b: list[int]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(1 for x, y in zip(a, b, strict=True) if x == y) / len(a)


def find_citations_near(text: str, start: int, end: int, window: int = 80) -> list[str]:
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    region = text[lo:hi]
    return [m.group(0) for m in CITE_RE.finditer(region)]


def is_quoted(text: str, start: int, end: int) -> bool:
    for m in QUOTE_RE.finditer(text):
        if m.start(1) <= start and m.end(1) >= end:
            return True
    span = text[max(0, start - 1) : min(len(text), end + 1)]
    return span.startswith(('"', "“")) and span.endswith(('"', "”"))


def looks_like_bibliography(section_title: str | None, passage: str) -> bool:
    title = (section_title or "").lower()
    if "reference" in title or "bibliograph" in title:
        return True
    # BibTeX / RIS-ish lines
    if passage.strip().startswith("@") or passage.strip().upper().startswith("TY  -"):
        return True
    return False


def is_common_phrase(passage: str) -> bool:
    norm = " ".join(tokenize(passage))
    if norm in COMMON_PHRASES:
        return True
    for phrase in COMMON_PHRASES:
        if phrase in norm and len(tokenize(passage)) <= 6:
            return True
    return False


def split_sentences(text: str) -> list[tuple[int, int, str]]:
    parts: list[tuple[int, int, str]] = []
    for m in re.finditer(r"[^.!?\n]+[.!?]?|\n+", text):
        chunk = m.group(0)
        if chunk.strip():
            parts.append((m.start(), m.end(), chunk.strip()))
    return parts


async def compare_texts(
    *,
    manuscript_text: str,
    sources: list[SourceDoc],
    profile: ThresholdProfile,
    section_title: str | None = None,
) -> list[RawMatch]:
    """Run ensemble methods against provided sources."""
    matches: list[RawMatch] = []
    ms_tokens = tokenize(manuscript_text)
    ms_word_ng = word_ngrams(ms_tokens, profile.word_ngram_n)
    ms_char_ng = char_ngrams(manuscript_text, profile.char_ngram_n)
    ms_sig = minhash_signature(ms_tokens)

    provider = get_embedding_provider()
    sentences = split_sentences(manuscript_text)
    sentence_texts = [s[2] for s in sentences]
    ms_vecs = await provider.embed(sentence_texts) if sentence_texts else []

    for source in sources:
        src_tokens = tokenize(source.text)
        if not src_tokens:
            continue
        src_word_ng = word_ngrams(src_tokens, profile.word_ngram_n)
        src_char_ng = char_ngrams(source.text, profile.char_ngram_n)
        src_sig = minhash_signature(src_tokens)
        mh = minhash_similarity(ms_sig, src_sig)
        wj = jaccard(ms_word_ng, src_word_ng)
        cj = jaccard(ms_char_ng, src_char_ng)

        # Candidate discovery via MinHash / n-gram thresholds
        candidate = (
            mh >= profile.minhash_threshold
            or wj >= profile.word_ngram_min_jaccard
            or cj >= profile.char_ngram_min_jaccard
        )
        if not candidate and source.kind not in {"internal_section", "authorized_prior_manuscript"}:
            # Still check exact phrases for short documents
            pass

        # Exact phrase matching: full sentences and long subspans inside sentences
        src_lower = source.text.lower()
        for start, end, sent in sentences:
            stokens = tokenize(sent)
            if len(stokens) < profile.exact_phrase_min_words:
                continue
            candidates: list[tuple[str, int, int]] = []
            # whole sentence
            candidates.append((" ".join(stokens), start, end))
            # sliding windows of tokens mapped approximately into the sentence
            for n in range(profile.exact_phrase_min_words, min(len(stokens), 20) + 1):
                for i in range(0, len(stokens) - n + 1):
                    phrase = " ".join(stokens[i : i + n])
                    if phrase in COMMON_PHRASES:
                        continue
                    local = re.search(re.escape(phrase), sent, flags=re.I)
                    if not local:
                        continue
                    candidates.append((phrase, start + local.start(), start + local.end()))
            hit = False
            for phrase, m_start, m_end in candidates:
                idx = src_lower.find(phrase)
                if idx < 0:
                    continue
                cites = find_citations_near(manuscript_text, m_start, m_end)
                span = manuscript_text[m_start:m_end]
                matches.append(
                    RawMatch(
                        manuscript_text=span,
                        manuscript_start=m_start,
                        manuscript_end=m_end,
                        source_key=source.key,
                        source_text=source.text[idx : idx + len(phrase)],
                        source_start=idx,
                        source_end=idx + len(phrase),
                        methods=["exact_phrase", "word_ngram"],
                        scores={
                            "exact": 1.0,
                            "word_ngram_jaccard": wj,
                            "char_ngram_jaccard": cj,
                            "minhash": mh,
                        },
                        citation_present=bool(cites),
                        citation_keys=cites,
                        in_quotes=is_quoted(manuscript_text, m_start, m_end),
                        is_bibliography=looks_like_bibliography(section_title, span),
                        is_common=is_common_phrase(span),
                        is_self=source.kind == "authorized_prior_manuscript",
                        is_internal=source.kind == "internal_section",
                    )
                )
                hit = True
                break
            if hit:
                continue

        # Near overlap from n-gram scores without exact phrase
        if candidate and wj >= profile.word_ngram_min_jaccard:
            # pick best overlapping sentence
            best_sent = None
            best_score = 0.0
            for start, end, sent in sentences:
                st = tokenize(sent)
                score = jaccard(word_ngrams(st, profile.word_ngram_n), src_word_ng)
                if score > best_score:
                    best_score = score
                    best_sent = (start, end, sent)
            if best_sent and best_score >= profile.word_ngram_min_jaccard:
                start, end, sent = best_sent
                if not any(
                    m.manuscript_start == start and m.source_key == source.key for m in matches
                ):
                    cites = find_citations_near(manuscript_text, start, end)
                    matches.append(
                        RawMatch(
                            manuscript_text=sent,
                            manuscript_start=start,
                            manuscript_end=end,
                            source_key=source.key,
                            source_text=source.text[:400],
                            source_start=0,
                            source_end=min(400, len(source.text)),
                            methods=["word_ngram", "char_ngram", "minhash"],
                            scores={
                                "word_ngram_jaccard": best_score,
                                "char_ngram_jaccard": cj,
                                "minhash": mh,
                            },
                            citation_present=bool(cites),
                            citation_keys=cites,
                            in_quotes=is_quoted(manuscript_text, start, end),
                            is_bibliography=looks_like_bibliography(section_title, sent),
                            is_common=is_common_phrase(sent),
                            is_self=source.kind == "authorized_prior_manuscript",
                            is_internal=source.kind == "internal_section",
                        )
                    )

        # Embedding semantic similarity per sentence
        if ms_vecs and source.text.strip():
            src_vec = (await provider.embed([source.text[:2000]]))[0]
            for (start, end, sent), vec in zip(sentences, ms_vecs, strict=False):
                if len(tokenize(sent)) < profile.short_phrase_max_words:
                    continue
                cos = cosine_similarity(vec, src_vec)
                if cos < profile.embedding_min_cosine:
                    continue
                # Reranker abstraction (identity score = cosine for now)
                rerank = cos
                if rerank < profile.rerank_min_score:
                    continue
                if any(
                    abs(m.manuscript_start - start) < 5 and m.source_key == source.key
                    for m in matches
                ):
                    # enrich existing
                    for m in matches:
                        if abs(m.manuscript_start - start) < 5 and m.source_key == source.key:
                            if "embedding" not in m.methods:
                                m.methods.append("embedding")
                            if "reranker" not in m.methods:
                                m.methods.append("reranker")
                            m.scores["embedding_cosine"] = cos
                            m.scores["rerank"] = rerank
                    continue
                cites = find_citations_near(manuscript_text, start, end)
                matches.append(
                    RawMatch(
                        manuscript_text=sent,
                        manuscript_start=start,
                        manuscript_end=end,
                        source_key=source.key,
                        source_text=source.text[:400],
                        source_start=0,
                        source_end=min(400, len(source.text)),
                        methods=["embedding", "reranker"],
                        scores={"embedding_cosine": cos, "rerank": rerank, "minhash": mh},
                        citation_present=bool(cites),
                        citation_keys=cites,
                        in_quotes=is_quoted(manuscript_text, start, end),
                        is_bibliography=looks_like_bibliography(section_title, sent),
                        is_common=is_common_phrase(sent),
                        is_self=source.kind == "authorized_prior_manuscript",
                        is_internal=source.kind == "internal_section",
                    )
                )

    return _dedupe_matches(matches)


def _dedupe_matches(matches: list[RawMatch]) -> list[RawMatch]:
    by_key: dict[tuple[str, int, int], RawMatch] = {}
    for m in matches:
        key = (m.source_key, m.manuscript_start, m.manuscript_end)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = m
            continue
        for method in m.methods:
            if method not in existing.methods:
                existing.methods.append(method)
        existing.scores.update(m.scores)
        existing.citation_present = existing.citation_present or m.citation_present
        existing.citation_keys = list({*existing.citation_keys, *m.citation_keys})
    return list(by_key.values())
