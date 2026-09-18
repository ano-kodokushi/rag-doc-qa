"""链路层：语料读取与入库编排（读 raw → 切分 → 落 chunks.jsonl → embedding → 写库）。

顶层**不得** import 任何第三方库；`pypdf` 只在 `read_raw_files` 内部延迟导入，
保证离线可 `import src.ingest`。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from src.chunking import Chunk, split_text
from src.config import load_settings
from src.embed import get_embedder
from src.store import VectorStore

if TYPE_CHECKING:  # 仅类型检查期
    from src.config import Settings

__all__ = ["RawDoc", "read_raw_files", "run_ingest", "build_parser", "main"]

_TEXT_SUFFIXES = {".md", ".txt"}
_PDF_SUFFIXES = {".pdf"}

# 说明文件（文件名，小写比较）：README 是「语料怎么放」的格式说明书，供人阅读，
# 不是知识本身。它被切块入库后，这类元信息会参与检索、挤占 top-k，稀释真实文档命中。
_NON_CORPUS_FILENAMES = frozenset({"readme.md", "readme.txt"})


def _is_non_corpus_file(path: Path) -> bool:
    """判断是否为说明文件（按文件名、大小写不敏感），这类文件不入语料库。"""
    return path.name.lower() in _NON_CORPUS_FILENAMES


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
    """遍历 `raw_dir` 下 *.md / *.txt / *.pdf（跳过 README 等说明文件），抽不出文本的文件跳过并警告；按文件名排序。"""
    docs: list[RawDoc] = []
    directory = Path(raw_dir)
    if not directory.is_dir():
        return docs

    candidates = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.lower() in (_TEXT_SUFFIXES | _PDF_SUFFIXES)
        and not _is_non_corpus_file(path)  # 说明文件不是语料
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


# ==================== CLI ====================

_MAX_SOURCES_PRINTED = 10


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.ingest",
        description="语料入库：读 data/raw → 切块 → 写 chunks.jsonl → embedding → 写向量库",
    )
    parser.add_argument(
        "--reset",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="入库前是否重建集合（默认开启；--no-reset 表示增量追加）",
    )
    parser.add_argument(
        "--raw-dir",
        default=None,
        help="覆盖语料目录，默认取 settings.raw_dir（即 data/raw）",
    )
    return parser


def _format_sources(sources: list[str]) -> str:
    if len(sources) <= _MAX_SOURCES_PRINTED:
        return ", ".join(sources)
    head = ", ".join(sources[:_MAX_SOURCES_PRINTED])
    return f"{head}, ...（共 {len(sources)} 个）"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    settings = load_settings()
    if args.raw_dir:
        settings = replace(settings, raw_dir=Path(args.raw_dir).resolve())

    summary = run_ingest(settings, reset=args.reset)

    print(
        "[info] 入库完成 "
        f"files={summary['files']} chunks={summary['chunks']} "
        f"elapsed_ms={summary['elapsed_ms']} mocked={summary['mocked']}"
    )
    print(f"[info] raw_dir={settings.raw_dir}")
    print(f"[info] sources: {_format_sources(summary['sources'])}")

    if summary["chunks"] == 0:
        print(
            f"[error] {settings.raw_dir} 下没有可入库文档，请先放入 .md/.txt/.pdf",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
