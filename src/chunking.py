"""切分层：把原始文档切成带标题归属的 Chunk。纯标准库、确定性。

契约见 SPEC §5 `src/chunking.py`。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# markdown 标题行：^#{1,6}\s
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")

# 段落分隔：一个或多个空行
_PARA_SPLIT = re.compile(r"\n\s*\n")


# ==================== 冻结数据结构 ====================


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    source: str
    heading: str
    index: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "source": self.source,
            "heading": self.heading,
            "index": self.index,
        }

    @staticmethod
    def from_dict(d: dict) -> "Chunk":
        return Chunk(
            id=str(d["id"]),
            text=str(d["text"]),
            source=str(d["source"]),
            heading=str(d.get("heading", "")),
            index=int(d.get("index", 0)),
        )


# ==================== 归一化 ====================


def normalize(text: str) -> str:
    """`\\r\\n`/`\\r` → `\\n`；去行尾空白；连续空行压成 1 个空行；整体 strip。"""
    if not text:
        return ""
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in unified.split("\n")]

    out: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run == 1:
                out.append("")
        else:
            blank_run = 0
            out.append(line)
    return "\n".join(out).strip()


# ==================== 切分 ====================


def _heading_of(line: str) -> str | None:
    """markdown 标题行返回标题文本（去掉 # 与首尾空白），否则 None。"""
    m = _HEADING_RE.match(line)
    if m is None:
        return None
    return m.group(2).strip()


def split_text(text: str, source: str, size: int = 400, overlap: int = 50) -> list[Chunk]:
    """按标题硬边界 + 段落装箱切分，确定性地返回 list[Chunk]。"""
    normalized = normalize(text)
    if not normalized.strip():
        return []

    # size 至少为 1，保证前进；overlap 非法（>= size 或 < 0）时视作 size // 4
    size = int(size)
    if size < 1:
        size = 1
    overlap = int(overlap)
    if overlap < 0 or overlap >= size:
        overlap = size // 4
    if overlap < 0:
        overlap = 0

    chunks: list[Chunk] = []
    heading = ""          # 当前归属标题
    buf_body = ""         # 当前 chunk 的正文（不含重叠前缀）
    buf_heading = ""      # 当前 chunk 生成时记录的标题
    prev_tail: str | None = None   # 上一个 chunk 末尾 overlap 个字符（仅用于跨 chunk 前缀）

    def current_text() -> str:
        if prev_tail:
            return prev_tail + buf_body
        return buf_body

    def flush() -> None:
        """结束当前 chunk；空 chunk 直接丢弃。"""
        nonlocal buf_body, buf_heading, prev_tail
        if not buf_body.strip():
            buf_body = ""
            return
        text_value = current_text()
        if not text_value.strip():
            buf_body = ""
            return
        index = len(chunks)
        chunks.append(
            Chunk(
                id=f"{source}#{index:04d}",
                text=text_value,
                source=source,
                heading=buf_heading,
                index=index,
            )
        )
        prev_tail = text_value[-overlap:] if overlap > 0 else ""
        buf_body = ""

    def start_chunk(new_heading: str, allow_overlap: bool = True) -> None:
        """开新 chunk。allow_overlap=False 时禁用重叠前缀（标题硬边界处）。"""
        nonlocal buf_body, buf_heading, prev_tail
        buf_body = ""
        buf_heading = new_heading
        if not allow_overlap:
            prev_tail = None
        elif prev_tail is not None and chunks and chunks[-1].heading == new_heading:
            pass  # 同一 section 内，保留 prev_tail 作为前缀
        else:
            prev_tail = None

    def available() -> int:
        """当前 chunk 正文还能放多少字符（前缀 + 正文合计不超过 size）。"""
        prefix_len = len(prev_tail) if prev_tail else 0
        return size - prefix_len - len(buf_body)

    def append_text(piece: str) -> None:
        """追加正文；加前缀后放不下时先落地当前 chunk，保证每块不超过 size。"""
        nonlocal buf_body, prev_tail
        if buf_body and len(piece) > available():
            flush()
        # 前缀本身已达 size 时无法承载任何正文，丢弃前缀避免必然超限
        if prev_tail is not None and len(prev_tail) >= size:
            prev_tail = None
        buf_body += piece

    def append_piece(piece: str, label: str) -> None:
        """按 size 硬切追加一段文本，保证单次追加必定前进，不会死循环。"""
        pos = 0
        while pos < len(piece):
            take = max(1, available())
            append_text(piece[pos:pos + take])
            pos += take
        assert buf_body, label  # 追加后 buffer 不可能为空

    lines = normalized.split("\n")
    i = 0
    total = len(lines)
    while i < total:
        line = lines[i]
        head = _heading_of(line)

        if head is not None:
            # 标题是硬边界：结束当前 chunk，开新 section
            # 标题变化即跨边界，新 section 的首块不带上一块的重叠前缀
            flush()
            heading = head
            start_chunk(heading, allow_overlap=False)
            # 标题行本身计入正文（过长则按 size 硬切，不丢字符）
            append_piece(line, "heading")
            i += 1
            continue

        if line.strip() == "":
            i += 1
            continue

        # 收集同一段落（非空行连续块）
        para_lines = []
        while i < total and lines[i].strip() != "" and _heading_of(lines[i]) is None:
            para_lines.append(lines[i])
            i += 1
        para = "\n".join(para_lines)

        if len(para) <= size:
            append_text(para)
        else:
            append_piece(para, "paragraph")
        continue

    flush()

    return [
        Chunk(
            id=f"{source}#{idx:04d}",
            text=c.text,
            source=source,
            heading=c.heading,
            index=idx,
        )
        for idx, c in enumerate(chunks)
    ]
