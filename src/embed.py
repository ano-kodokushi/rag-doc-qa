"""向量化模块。

- `Embedder`：调用 OpenAI 兼容的 /v1/embeddings 接口（**延迟导入 openai**）。
- `MockEmbedder`：纯标准库（hashlib）的离线哈希向量，不联网、不读 API key。

硬约束：本模块顶层不得 import 任何第三方库（离线必须能 `import src.embed`）。
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 仅用于类型标注，运行时不导入
    from src.config import Settings


# ────────────────────────────── 真实 Embedder ──────────────────────────────


class Embedder:
    """基于 OpenAI 兼容接口的向量化实现。"""

    def __init__(self, settings: "Settings") -> None:
        self.settings = settings
        if not settings.embed_api_key:
            raise RuntimeError("EMBED_API_KEY 未配置")
        # 延迟导入：离线环境（未安装 openai）也必须能 import 本模块
        from openai import OpenAI

        self.client = OpenAI(
            base_url=settings.embed_base_url,
            api_key=settings.embed_api_key,
        )

    # ── 内部：单批调用，失败重试 1 次 ──
    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        last_err: Exception | None = None
        for _ in range(2):  # 首次 + 重试 1 次
            try:
                resp = self.client.embeddings.create(
                    model=self.settings.embed_model,
                    input=batch,
                )
                ordered: list[list[float] | None] = [None] * len(batch)
                for i, item in enumerate(resp.data):
                    idx = getattr(item, "index", i)
                    if not isinstance(idx, int) or idx < 0 or idx >= len(batch):
                        idx = i
                    ordered[idx] = list(item.embedding)
                if any(v is None for v in ordered):
                    raise ValueError("embedding 响应条目数少于输入条数")
                return [v for v in ordered if v is not None]
            except Exception as exc:  # noqa: BLE001 - 统一转为 RuntimeError
                last_err = exc
        raise RuntimeError(f"EMBED 请求失败（已重试 1 次）：{last_err}")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """按 settings.embed_batch 分批向量化，返回顺序与输入一致。"""
        texts = list(texts)
        if not texts:
            return []
        batch_size = max(1, int(self.settings.embed_batch))
        out: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            out.extend(self._embed_batch(texts[start : start + batch_size]))
        return out

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_texts([text])
        if not vectors:
            return []
        return vectors[0]


# ────────────────────────────── Mock Embedder ──────────────────────────────


class MockEmbedder:
    """纯标准库的确定性哈希向量（离线可用）。

    做法：对字符 1-gram + 2-gram 做哈希落到 embed_dim 个桶里计数，再 L2 归一化。
    共享字词越多的两段文本，余弦相似度越高。
    """

    def __init__(self, settings: "Settings") -> None:
        self.settings = settings
        self.dim = int(settings.embed_dim)

    # ── 内部：取字符 n-gram（1-gram + 2-gram） ──
    @staticmethod
    def _grams(text: str) -> list[str]:
        chars = list(text)
        grams = list(chars)
        for i in range(len(chars) - 1):
            grams.append(chars[i] + chars[i + 1])
        return grams

    def _bucket(self, gram: str) -> int:
        digest = hashlib.md5(gram.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") % self.dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for gram in self._grams(text):
            vec[self._bucket(gram)] += 1.0
        norm = sum(v * v for v in vec) ** 0.5
        if norm == 0.0:
            # 空串/纯空白：不得返回全零向量
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        texts = list(texts)
        if not texts:
            return []
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def get_embedder(settings: "Settings") -> Embedder | MockEmbedder:
    """mock 模式返回 MockEmbedder，否则返回 Embedder。"""
    if settings.mock:
        return MockEmbedder(settings)
    return Embedder(settings)
