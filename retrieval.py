"""Hybrid retrieval utilities shared by public and hidden-style evaluations."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9#@._-]+")
_STOP_WORDS = {
    "ai",
    "bao",
    "bi",
    "boi",
    "cai",
    "can",
    "cho",
    "co",
    "cua",
    "duoc",
    "gi",
    "khi",
    "khong",
    "la",
    "luc",
    "mot",
    "nao",
    "neu",
    "nhieu",
    "nhung",
    "sau",
    "theo",
    "thi",
    "trong",
    "tu",
    "va",
    "voi",
}
_ALIASES = {
    "capnhat": {"update", "updated", "updating"},
    "chuyencap": {"escalate", "escalated", "escalation"},
    "khacphuc": {"resolve", "resolved", "resolution"},
    "benlienquan": {"stakeholder", "stakeholders"},
    "phanhoi": {"response"},
    "matkhau": {"password"},
    "hoantien": {"refund"},
}


def _ascii_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _tokens(value: str) -> list[str]:
    ascii_value = _ascii_text(value)
    phrase_aliases = {
        "cap nhat": "capnhat",
        "chuyen cap": "chuyencap",
        "khac phuc": "khacphuc",
        "ben lien quan": "benlienquan",
        "phan hoi": "phanhoi",
        "mat khau": "matkhau",
        "hoan tien": "hoantien",
    }
    for phrase, alias in phrase_aliases.items():
        ascii_value = ascii_value.replace(phrase, f" {alias} ")

    alias_lookup = {
        variant: canonical
        for canonical, variants in _ALIASES.items()
        for variant in variants
    }
    result: list[str] = []
    for token in _TOKEN_RE.findall(ascii_value):
        canonical = alias_lookup.get(token, token)
        if len(canonical) > 1 and canonical not in _STOP_WORDS:
            result.append(canonical)
    return result


def _lexical_scores(query: str, documents: list[str]) -> list[float]:
    query_counts = Counter(_tokens(query))
    if not query_counts:
        return [0.0] * len(documents)

    document_tokens = [set(_tokens(document)) for document in documents]
    document_frequency = Counter(
        token for tokens in document_tokens for token in tokens
    )
    candidate_count = max(len(documents), 1)

    weights = {
        token: math.log((candidate_count + 1) / (document_frequency[token] + 1)) + 1.0
        for token in query_counts
    }
    denominator = sum(weights[token] * count for token, count in query_counts.items())
    scores: list[float] = []
    for tokens in document_tokens:
        matched = sum(
            weights[token] * count
            for token, count in query_counts.items()
            if token in tokens
        )
        scores.append(matched / denominator if denominator else 0.0)
    return scores


def hybrid_query(collection: Any, query_text: str, n_results: int) -> dict[str, list[list[Any]]]:
    """Retrieve vector candidates, then rerank without using evaluation labels."""
    collection_size = int(collection.count())
    if collection_size == 0:
        return {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}

    candidate_count = min(collection_size, max(n_results * 5, 20))
    result = collection.query(
        query_texts=[query_text],
        n_results=candidate_count,
        include=["documents", "metadatas", "distances"],
    )
    documents = list((result.get("documents") or [[]])[0])
    metadatas = list((result.get("metadatas") or [[]])[0])
    distances = list((result.get("distances") or [[]])[0])
    ids = list((result.get("ids") or [[]])[0])
    lexical = _lexical_scores(query_text, documents)

    ranked = sorted(
        range(len(documents)),
        key=lambda index: distances[index] - lexical[index],
    )[:n_results]
    return {
        "documents": [[documents[index] for index in ranked]],
        "metadatas": [[metadatas[index] for index in ranked]],
        "distances": [[distances[index] for index in ranked]],
        "ids": [[ids[index] for index in ranked]] if ids else [[]],
    }
