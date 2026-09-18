"""BM25 关键词检索（jieba / rank_bm25 **延迟导入**）。

硬约束：顶层不得 import jieba / rank_bm25，离线必须能 `import src.bm25`。
"""

from __future__ import annotations

import json
from pathlib import Path

from src.chunking import Chunk
from src.fusion import Hit


def _tokenize(text: str) -> list[str]:
    """延迟导入 jieba 后分词。"""
    import jieba

    return [t for t in jieba.lcut(text) if t.strip()]


class KeywordIndex:
    """基于 rank_bm25 的关键词索引。"""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks: list[Chunk] = list(chunks)
        self._tokens: list[list[str]] = [_tokenize(c.text) for c in self.chunks]
        self._bm25 = None
        if self._tokens:
            # 延迟导入：离线环境（未安装 rank_bm25）也必须能 import 本模块
            from rank_bm25 import BM25Okapi

            self._bm25 = BM25Okapi(self._tokens)

    @classmethod
    def from_chunks_file(cls, path: Path) -> "KeywordIndex":
        path = Path(path)
        if not path.exists():
            return cls([])
        chunks: list[Chunk] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    chunks.append(Chunk.from_dict(json.loads(line)))
                except Exception:  # noqa: BLE001 - 坏行跳过
                    continue
        return cls(chunks)

    def search(self, query: str, top_k: int) -> list[Hit]:
        if not query or not query.strip():
            return []
        if not self.chunks or self._bm25 is None or top_k <= 0:
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = list(self._bm25.get_scores(tokens))
        hits = [
            Hit(
                chunk_id=c.id,
                text=c.text,
                source=c.source,
                heading=c.heading,
                score=float(scores[i]),
                retriever="bm25",
            )
            for i, c in enumerate(self.chunks)
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    def size(self) -> int:
        return len(self.chunks)
