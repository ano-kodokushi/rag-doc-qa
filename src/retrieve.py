"""链路层：检索编排（向量 + BM25 → RRF 融合 → 可选 rerank）。

顶层**不得** import 任何第三方库（chromadb / openai / requests / pypdf 等），
`requests` 只在 `Retriever._rerank` 内部延迟导入，保证离线可 `import src.retrieve`。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.bm25 import KeywordIndex
from src.chunking import Chunk
from src.embed import get_embedder
from src.fusion import Hit, rrf_fuse
from src.store import VectorStore

if TYPE_CHECKING:  # 仅类型检查期，无任何运行期耦合
    from src.config import Settings

__all__ = ["Retriever"]


class Retriever:
    """两路召回 + RRF 融合（+ 可选远端 rerank）的检索器。"""

    def __init__(self, settings: "Settings") -> None:
        self.settings = settings
        self.embedder = get_embedder(settings)
        self.store = VectorStore(settings)

    # ── 内部工具 ───────────────────────────────────────────────────────────

    def _chunk_map(self) -> dict[str, Chunk]:
        """以 `VectorStore.all_chunks()`（读 chunks_file）为权威来源建 id → Chunk 映射。"""
        mapping: dict[str, Chunk] = {}
        for chunk in self.store.all_chunks():
            mapping[chunk.id] = chunk
        return mapping

    def _rankings(self, question: str) -> dict[str, list[str]]:
        """两路召回的 id 排名（rank 从 1 开始，交给 rrf_fuse 计分）。"""
        vector_hits = self.store.query(
            self.embedder.embed_query(question), self.settings.top_k_vec
        )
        keyword_index = KeywordIndex.from_chunks_file(self.settings.chunks_file)
        bm25_hits = keyword_index.search(question, self.settings.top_k_bm25)
        return {
            "vector": [hit.chunk_id for hit in vector_hits],
            "bm25": [hit.chunk_id for hit in bm25_hits],
        }

    @staticmethod
    def _fused_hits(
        rankings: dict[str, list[str]], chunk_map: dict[str, Chunk]
    ) -> tuple[list[str], list[Hit]]:
        """RRF 融合，并把 id 还原成完整 Hit（retriever="fused"）。

        返回 (融合顺序的全量 id 列表, 能还原出 Chunk 的 Hit 列表)；映射里找不到的 id 直接丢弃。
        """
        fused = rrf_fuse(rankings)
        fused_ids = [chunk_id for chunk_id, _score in fused]
        hits: list[Hit] = []
        for chunk_id, score in fused:
            chunk = chunk_map.get(chunk_id)
            if chunk is None:
                continue
            hits.append(
                Hit(
                    chunk_id=chunk.id,
                    text=chunk.text,
                    source=chunk.source,
                    heading=chunk.heading,
                    score=score,
                    retriever="fused",
                )
            )
        return fused_ids, hits

    def _rerank(self, question: str, hits: list[Hit], top_n: int) -> list[Hit]:
        """远端 rerank。任何异常都由调用方吞掉并降级为融合结果。"""
        # ⚠️ 字段名以官方文档为准：以下 `input.query` / `input.documents` /
        # `parameters.top_n` 请求体，以及 `output.results[i].index` /
        # `.relevance_score` 响应解析，取自阿里云百炼 Text Rerank（gte-rerank-v2）
        # 官方 HTTP 契约。若官方字段调整，此处会抛异常 → 上层降级，不会让问答报错。
        import requests  # 延迟导入：未安装 requests 也能 import 本模块

        api_key = self.settings.rerank_api_key or self.settings.embed_api_key
        payload = {
            "model": self.settings.rerank_model,
            "input": {"query": question, "documents": [hit.text for hit in hits]},
            "parameters": {"top_n": top_n},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            self.settings.rerank_url, json=payload, headers=headers, timeout=30
        )
        resp.raise_for_status()
        results = resp.json()["output"]["results"]

        scored: list[tuple[float, int, Hit]] = []
        for item in results:
            index = int(item["index"])
            if index < 0 or index >= len(hits):
                continue
            score = float(item["relevance_score"])
            src = hits[index]
            scored.append(
                (
                    score,
                    index,
                    Hit(
                        chunk_id=src.chunk_id,
                        text=src.text,
                        source=src.source,
                        heading=src.heading,
                        score=score,
                        retriever="rerank",
                    ),
                )
            )
        # 按 score 降序；同分保留原序（index 升序），保证确定性
        scored.sort(key=lambda row: (-row[0], row[1]))
        return [row[2] for row in scored]

    # ── 公开接口 ───────────────────────────────────────────────────────────

    def search(
        self,
        question: str,
        top_k: int | None = None,
        use_rerank: bool | None = None,
    ) -> list[Hit]:
        """向量 + BM25 → RRF 融合 → 取 top_k（默认 settings.top_k_final）。"""
        if not question or not question.strip():
            return []

        top_k_final = self.settings.top_k_final if top_k is None else top_k
        if top_k_final <= 0:
            return []

        rankings = self._rankings(question)
        _fused_ids, fused_hits = self._fused_hits(rankings, self._chunk_map())

        do_rerank = self.settings.rerank_enabled if use_rerank is None else use_rerank
        if do_rerank and not self.settings.mock and fused_hits:
            try:
                reranked = self._rerank(question, fused_hits, top_k_final)
                if reranked:
                    return reranked[:top_k_final]
            except Exception as exc:  # rerank 失败必须降级，绝不能抛给上层
                print(f"[warn] rerank 降级: {exc}")

        return fused_hits[:top_k_final]

    def debug(self, question: str) -> dict:
        """返回 {"vector":[id...],"bm25":[id...],"fused":[id...],"final":[id...]}。"""
        if not question or not question.strip():
            return {"vector": [], "bm25": [], "fused": [], "final": []}

        rankings = self._rankings(question)
        fused_ids, fused_hits = self._fused_hits(rankings, self._chunk_map())
        top_k_final = self.settings.top_k_final
        final_ids = [hit.chunk_id for hit in fused_hits[:top_k_final]] if top_k_final > 0 else []

        return {
            "vector": rankings["vector"],
            "bm25": rankings["bm25"],
            "fused": fused_ids,
            "final": final_ids,
        }
