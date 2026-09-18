"""向量库封装（chromadb，**延迟导入**）。

硬约束：
- 顶层不得 import chromadb（离线必须能 `import src.store`）。
- 严禁使用 chromadb 默认 embedding function（会联网下载 ONNX 模型），
  `upsert` 必须显式传 `embeddings=`，`query` 必须显式传 `query_embeddings=`。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.chunking import Chunk
from src.fusion import Hit

if TYPE_CHECKING:  # 仅用于类型标注，运行时不导入
    from src.config import Settings


class VectorStore:
    """chromadb 持久化集合的薄封装。"""

    def __init__(self, settings: "Settings") -> None:
        self.settings = settings
        # 延迟导入：离线环境（未安装 chromadb）也必须能 import 本模块
        import chromadb

        self.client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        self.collection = self.client.get_or_create_collection(
            name=settings.collection,
            metadata={"hnsw:space": "cosine"},
        )

    # ── 清库重建 ──
    def reset(self) -> None:
        try:
            self.client.delete_collection(name=self.settings.collection)
        except Exception:  # noqa: BLE001 - 集合不存在时忽略
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.settings.collection,
            metadata={"hnsw:space": "cosine"},
        )

    # ── 写入 ──
    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        chunks = list(chunks)
        embeddings = list(embeddings)
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks 与 embeddings 长度不等：{len(chunks)} != {len(embeddings)}"
            )
        if not chunks:
            return 0
        ids = [c.id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {"source": c.source, "heading": c.heading, "index": c.index} for c in chunks
        ]
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        return len(chunks)

    # ── 检索 ──
    def query(self, embedding: list[float], top_k: int) -> list[Hit]:
        if top_k <= 0:
            return []
        res = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        ids = (res.get("ids") or [[]])[0] or []
        documents = (res.get("documents") or [[]])[0] or []
        metadatas = (res.get("metadatas") or [[]])[0] or []
        distances = (res.get("distances") or [[]])[0] or []

        hits: list[Hit] = []
        for i, cid in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            distance = distances[i] if i < len(distances) else 0.0
            hits.append(
                Hit(
                    chunk_id=str(cid),
                    text=str(documents[i]) if i < len(documents) else "",
                    source=str(meta.get("source", "")),
                    heading=str(meta.get("heading", "")),
                    score=1.0 - float(distance),
                    retriever="vector",
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    def count(self) -> int:
        return int(self.collection.count())

    # ── 权威来源：chunks.jsonl ──
    def all_chunks(self) -> list[Chunk]:
        path = self.settings.chunks_file
        if not path.exists():
            return []
        chunks: list[Chunk] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    chunks.append(Chunk.from_dict(data))
                except Exception:  # noqa: BLE001 - 坏行跳过
                    continue
        return chunks
