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

__all__ = ["Retriever", "dedupe_by_section", "expand_to_sections"]

#: 小节内各块拼接时的分隔符（`\n\n`，与切分层的段落边界同形）
_SECTION_JOIN = "\n\n"

#: `settings.section_mode` 的合法取值（`off` / `diverse` / `expand`）。
#: 真正的合法性校验在 `src/config.py`，这里只声明检索层认识哪几种模式；
#: 取值不在其中时 `Retriever._finalize` 按 `off` 处理（安全默认）。
SECTION_MODES = ("off", "diverse", "expand")


def dedupe_by_section(hits: list[Hit]) -> list[Hit]:
    """按 `(source, heading)` 去重，每个小节只保留**首次出现**（排名最高）的那一块。

    动机（T-020 修订 / 实测）：`expand` 把小节撑长会撞上 prompt 的 `max_chars` 硬截断
    （当时的契约默认值是 3000；**T-028 Step 4 已改为 6000**，但本条实测数字仍按当时口径记录）
    （`SECTION_EXPAND=ON` 时 4/20 题被截断，prompt 最大 4742 字符）；而把缺失要点
    定位到它真正所在的小节后发现，**主导失分模式是「需要的内容在同一文档的另一个小节」**
    （`q03` / `q13` 的缺失要点全在另一节，扩展命中块那一节毫无用处）。所以真正该做的是让
    top-k 覆盖**更多不同的 `(文档, 小节)`**，而不是把小节撑长 —— 本函数只做去重，`text`
    原样返回、不扩展。

    契约：
    - 去重键 `(source, heading)`，保留首次出现的那一条（即融合排名最高的那一条）；
    - `text` / `chunk_id` / `score` / `retriever` / `heading` **全部原样保留**
      （不扩展、不改 id、不改分）；
    - 保持首次出现顺序；空输入返回 `[]`；确定性；不修改传入的 hits（也不依赖它们的可变性）；
    - 纯标准库，不依赖任何第三方库。
    """
    seen_sections: set[tuple[str, str]] = set()
    deduped: list[Hit] = []

    for hit in hits:
        section_key = (hit.source, hit.heading)
        if section_key in seen_sections:
            continue
        seen_sections.add(section_key)
        deduped.append(hit)

    return deduped


def expand_to_sections(hits: list[Hit], chunk_map: dict[str, Chunk]) -> list[Hit]:
    """把每个命中块扩展成「它所在的小节」，并按小节去重（T-020 / EXPERIMENTS E-02）。

    动机：多跳题与部分单跳题的失分不是文件级召回不够，而是**检索到的是同一文件的
    错误小节**（`q03` / `q14` 模型答"资料里没有"，而答案就在同文件另一节里），
    所以命中一个块时要把 `source` + `heading` 相同的**全部块**一并给模型。

    ⚠️ 实测代价（T-020 修订）：拼出的小节会撞上 prompt 的 `max_chars` 硬截断
    （当时默认 3000，**T-028 Step 4 已改为 6000**），
    所以本函数只在 `SECTION_MODE=expand` 时启用；要「覆盖更多小节」而不撑长 prompt
    应当用 `SECTION_MODE=diverse`（见 `dedupe_by_section`）。

    契约：
    - 先去重（`dedupe_by_section`，同小节只留首次命中那条），再对留下的每条取
      `chunk_map` 里同 `source` 且同 `heading` 的块，按 `index` 升序用 `\\n\\n` 拼成
      小节全文，替换该 hit 的 `text`；
    - `score` / `retriever` 取首次命中的值；
    - `chunk_id` 保持「首次命中的那个 chunk」的 id，**不改成小节 id** ——
      `eval/metrics.py` 的 `hit_at_k` 靠 `chunk_id` 前缀匹配 `gold_sources`，
      改成小节 id 会静默破坏全部历史指标的可比性；
    - `heading` 保持不变；`chunk_map` 里找不到该 hit 的 `chunk_id` 时**原样保留**（不丢、不报错）；
    - 空输入返回 `[]`；纯标准库，不依赖任何第三方库。
    """
    expanded: list[Hit] = []

    for hit in dedupe_by_section(hits):
        if hit.chunk_id not in chunk_map:
            expanded.append(hit)
            continue

        section_chunks = sorted(
            (
                chunk
                for chunk in chunk_map.values()
                if chunk.source == hit.source and chunk.heading == hit.heading
            ),
            key=lambda chunk: chunk.index,
        )
        if not section_chunks:
            expanded.append(hit)
            continue

        expanded.append(
            Hit(
                chunk_id=hit.chunk_id,
                text=_SECTION_JOIN.join(chunk.text for chunk in section_chunks),
                source=hit.source,
                heading=hit.heading,
                score=hit.score,
                retriever=hit.retriever,
            )
        )

    return expanded


class Retriever:
    """两路召回 + RRF 融合（+ 可选远端 rerank）的检索器。"""

    def __init__(self, settings: "Settings") -> None:
        self.settings = settings
        self.embedder = get_embedder(settings)
        self.store = VectorStore(settings)
        # 进程内缓存（惰性构建、实例级）：chunks_file 读盘 + BM25 索引 + id→Chunk 映射
        # 都只做一次，避免每次 search 重建索引（原为检索耗时的大头）。
        self._keyword_index: KeywordIndex | None = None
        self._chunk_map_cache: dict[str, Chunk] | None = None

    # ── 缓存失效 ───────────────────────────────────────────────────────────

    def clear_cache(self) -> None:
        """丢弃进程内缓存的 BM25 索引与 chunk 映射，下次使用时惰性重建。

        ⚠️ 本缓存是**进程内**的，以 `settings.chunks_file` 的构建时刻为准：
        只要语料发生变更（重新 ingest、chunks.jsonl 被改写），**必须**调用本方法
        失效，否则会继续用旧索引作答。`app/main.py` 的 `/ingest` 已通过
        `get_retriever.cache_clear()` 丢弃整个 Retriever，因此走 HTTP 路径时
        无需额外调用。
        """
        self._keyword_index = None
        self._chunk_map_cache = None

    # ── 内部工具 ───────────────────────────────────────────────────────────

    def _keyword_index_cached(self) -> KeywordIndex:
        """取缓存的 BM25 索引；首次调用时从 chunks_file 构建。"""
        if self._keyword_index is None:
            self._keyword_index = KeywordIndex.from_chunks_file(
                self.settings.chunks_file
            )
        return self._keyword_index

    def _chunk_map(self) -> dict[str, Chunk]:
        """以 `VectorStore.all_chunks()`（读 chunks_file）为权威来源建 id → Chunk 映射。

        结果缓存在实例上；语料变更后需 `clear_cache()` 失效。
        """
        if self._chunk_map_cache is None:
            mapping: dict[str, Chunk] = {}
            for chunk in self.store.all_chunks():
                mapping[chunk.id] = chunk
            self._chunk_map_cache = mapping
        return self._chunk_map_cache

    def _rankings(self, question: str) -> dict[str, list[str]]:
        """两路召回的 id 排名（rank 从 1 开始，交给 rrf_fuse 计分）。"""
        vector_hits = self.store.query(
            self.embedder.embed_query(question), self.settings.top_k_vec
        )
        keyword_index = self._keyword_index_cached()
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
        """向量 + BM25 → RRF 融合 → 取 top_k（默认 settings.top_k_final）→ 按 `section_mode` 整理。

        `settings.section_mode` 三模式（T-020 修订）：
        - `off`：top-k 的块原样返回；
        - `diverse`：按 `(source, heading)` 去重，每个小节只留排名最高的那一块，`text` 不扩展；
        - `expand`：去重 + 把 `text` 换成该小节全文。

        ⚠️ 顺序不能反：**先取 top-k，再按 mode 整理**。先去重再截断会改变 `top_k` 的语义
        （去重发生在候选集上而非最终结果上）。整理后条数可能少于 `top_k`，这是预期行为。
        签名与返回类型不受影响。
        """
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
                    return self._finalize(reranked[:top_k_final])
            except Exception as exc:  # rerank 失败必须降级，绝不能抛给上层
                print(f"[warn] rerank 降级: {exc}")

        return self._finalize(fused_hits[:top_k_final])

    def _finalize(self, hits: list[Hit]) -> list[Hit]:
        """对**已取好 top_k** 的结果按 `section_mode` 整理（`off` 或未知值原样返回）。

        未知值在 `src/config.py` 已被回退成 `off`，这里再兜一层：检索层不认识的值一律按
        `off` 处理，绝不让配置写错把整个服务搞挂。
        """
        mode = self.settings.section_mode
        if mode == "diverse":
            return dedupe_by_section(hits)
        if mode == "expand":
            return expand_to_sections(hits, self._chunk_map())
        return hits

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
