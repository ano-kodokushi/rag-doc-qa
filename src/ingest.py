"""链路层：语料读取与入库编排（读 raw → 切分 → 落 chunks.jsonl → embedding → 写库）。

顶层**不得** import 任何第三方库；`pypdf` 只在 `read_raw_files` 内部延迟导入，
保证离线可 `import src.ingest`。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from src.chunking import Chunk, split_text
from src.embed import get_embedder
from src.store import VectorStore

if TYPE_CHECKING:  # 仅类型检查期
    from src.config import Settings

__all__ = ["RawDoc", "read_raw_files", "run_ingest"]

_TEXT_SUFFIXES = {".md", ".txt"}
_PDF_SUFFIXES = {".pdf"}


@dataclass
class RawDoc:
    source: str
    text: str


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_pdf_file(path: Path) -> str:
    from pypdf import PdfReader  # 延迟导入

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text:
            parts.append(page_text)
    return "\n".join(parts)


def read_raw_files(raw_dir: Path) -> list[RawDoc]:
    """遍历 `raw_dir` 下 *.md / *.txt / *.pdf，抽不出文本的文件跳过并警告；按文件名排序。"""
    docs: list[RawDoc] = []
    directory = Path(raw_dir)
    if not directory.is_dir():
        return docs

    candidates = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.lower() in (_TEXT_SUFFIXES | _PDF_SUFFIXES)
    ]
    candidates.sort(key=lambda path: path.name)  # 确定性：按文件名排序

    for path in candidates:
        suffix = path.suffix.lower()
        try:
            if suffix in _PDF_SUFFIXES:
                text = _read_pdf_file(path)
            else:
                text = _read_text_file(path)
        except Exception as exc:  # 单个文件失败不影响整体入库
            print(f"[warn] 跳过无法解析的文件 {path.name}: {exc}")
            continue
        if not text or not text.strip():
            print(f"[warn] 跳过抽不出文本的文件 {path.name}")
            continue
        docs.append(RawDoc(source=path.name, text=text))
    return docs


def _write_chunks(path: Path, chunks: list[Chunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for chunk in chunks:
            fp.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")


def run_ingest(settings: "Settings", reset: bool = True) -> dict:
    """读取 → 切分 → 写 chunks.jsonl → embedding → (reset) → upsert。"""
    started = time.perf_counter()
    settings.chunks_file.parent.mkdir(parents=True, exist_ok=True)

    docs = read_raw_files(settings.raw_dir)

    chunks: list[Chunk] = []
    for doc in docs:
        chunks.extend(
            split_text(
                doc.text,
                doc.source,
                size=settings.chunk_size,
                overlap=settings.chunk_overlap,
            )
        )

    # 无论是否为空，都写出（可为空文件）chunks.jsonl，保证后续链路有确定输入
    _write_chunks(settings.chunks_file, chunks)

    if not chunks:
        print("[warn] data/raw 下没有可入库文档")
        return {
            "files": len(docs),
            "chunks": 0,
            "sources": [doc.source for doc in docs],
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "mocked": bool(settings.mock),
        }

    embedder = get_embedder(settings)
    embeddings = embedder.embed_texts([chunk.text for chunk in chunks])

    store = VectorStore(settings)
    if reset:
        store.reset()
    store.upsert(chunks, embeddings)

    return {
        "files": len(docs),
        "chunks": len(chunks),
        "sources": [doc.source for doc in docs],
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "mocked": bool(settings.mock),
    }
