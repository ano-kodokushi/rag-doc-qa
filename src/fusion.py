"""融合层：RRF 融合与保序去重。纯标准库、确定性。

契约见 SPEC §5 `src/fusion.py`。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    text: str
    source: str
    heading: str
    score: float
    retriever: str  # "vector" | "bm25" | "fused" | "rerank"


def dedupe_keep_order(items: list[str]) -> list[str]:
    """按首次出现顺序去重（保持确定性，不依赖 set 迭代序）。"""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def rrf_fuse(rankings: dict[str, list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion。

    score = Σ_retriever 1/(k + rank)，rank 从 1 开始；
    同一 list 内重复 id 只计首次出现的 rank；
    按 score 降序，score 相同时按 chunk_id 字典序升序；
    空输入返回 []。
    """
    scores: dict[str, float] = {}

    for retriever in rankings:
        ranking = rankings[retriever]
        if not ranking:
            continue
        seen: set[str] = set()
        rank = 0
        for chunk_id in ranking:
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            rank += 1
            contribution = 1.0 / (k + rank)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + contribution

    # 主键：score 降序；次键：chunk_id 字典序升序
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(chunk_id, score) for chunk_id, score in ordered]
