"""FastAPI 服务入口（SPEC §5 `app/main.py` 冻结接口）。

冻结路由：
    GET  /health   -> {"status":"ok","mock":bool,"chunks":int}
    POST /ingest   body {"reset": true} -> run_ingest 结果
    POST /chat     body {"question": str, "top_k": int|null}
                   -> {"answer","citations","hits","latency_ms","mocked"}

设计要点：
- 启动时不建索引（lazy）：只有 `/chat` 首次被调用时才构建 `Retriever` / `Generator` 并缓存。
- `question` 为空或非字符串 -> HTTP 400。
- 检索结果为空时仍然走生成（由 MockGenerator / Generator 给出"根据现有资料无法回答"级别的结果），不报 500。
- SPEC §2 例外：本文件允许顶层 `from fastapi import FastAPI`（该文件不参与离线单测）。

可直接 `python -m app.main` 或 `python app/main.py` 启动。
"""

from __future__ import annotations

import sys
import time
from functools import lru_cache
from pathlib import Path

# __file__ = <项目根>/app/main.py，向上两级即项目根。
# 需要把项目根放进 sys.path，才能以脚本方式直接运行时 import 到同级的 `src` 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src.config import Settings, load_settings  # noqa: E402
from src.fusion import Hit  # noqa: E402
from src.generate import get_generator  # noqa: E402
from src.ingest import run_ingest  # noqa: E402
from src.retrieve import Retriever  # noqa: E402

app = FastAPI(title="rag-doc-qa", version="1.0.0")

# 二期前端要跨源访问；不加登录/鉴权/限流/缓存（SPEC 范围内不做）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- 请求体模型


class IngestRequest(BaseModel):
    """POST /ingest 请求体。"""

    reset: bool = True


class ChatRequest(BaseModel):
    """POST /chat 请求体；`top_k` 允许为 None（用 settings.top_k_final）。"""

    question: str                      # 必填；空串会在处理函数里被拒为 400
    top_k: int | None = None


# ---------------------------------------------------------------- 懒加载缓存


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """加载并缓存 Settings。"""
    return load_settings()


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    """构建并缓存 Retriever（首次 /chat 时才建，启动不建索引）。"""
    return Retriever(get_settings())


@lru_cache(maxsize=1)
def get_cached_generator():
    """构建并缓存 Generator / MockGenerator。"""
    return get_generator(get_settings())


def count_chunks() -> int:
    """`/health` 用：已入库 chunk 数。

    这是只读计数，不会构建索引；任何异常都不该让健康检查挂掉，失败时返回 0。
    """
    from src.store import VectorStore  # 延迟导入：/health 不该因第三方库缺失而报错

    try:
        return int(VectorStore(get_settings()).count())
    except Exception as exc:  # pragma: no cover - 依赖运行环境
        print(f"[warn] /health 读取 chunk 数失败：{exc}")
        return 0


# ---------------------------------------------------------------- 路由


@app.get("/health")
def health() -> dict:
    """健康检查：返回运行模式与当前已入库 chunk 数。"""
    return {
        "status": "ok",
        "mock": bool(get_settings().mock),
        "chunks": count_chunks(),
    }


@app.post("/ingest")
def ingest(payload: IngestRequest | None = None) -> dict:
    """执行入库；body 省略或 `{"reset": true}` 时先清空旧集合。"""
    reset = True if payload is None else bool(payload.reset)
    result = run_ingest(get_settings(), reset=reset)
    # 重新入库后，之前缓存的检索器/生成器持有的语料快照可能过期，清掉让下次 /chat 重建。
    get_retriever.cache_clear()
    return result


@app.post("/chat")
def chat(payload: ChatRequest) -> dict:
    """检索 + 生成。检索为空时仍然走生成（不报 500）。"""
    question = payload.question
    if not isinstance(question, str) or not question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    # 首次调用时才构建 Retriever / Generator（lazy），之后复用缓存。
    retriever = get_retriever()
    generator = get_cached_generator()

    started = time.perf_counter()
    hits: list[Hit] = retriever.search(question, top_k=payload.top_k)
    answer = generator.answer(question, hits)

    # 检索为空时 answer.text 由 Generator / MockGenerator 给出拒答文案，这里不做特判、不报错。
    latency_ms = int(answer.latency_ms) if answer.latency_ms is not None else int(
        (time.perf_counter() - started) * 1000
    )

    return {
        "answer": answer.text,
        "citations": list(answer.citations),
        "hits": [
            {
                "chunk_id": h.chunk_id,
                "source": h.source,
                "heading": h.heading,
                "score": h.score,
                "retriever": h.retriever,
            }
            for h in hits
        ],
        "latency_ms": latency_ms,
        "mocked": bool(answer.mocked),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
