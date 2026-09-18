"""链路层：Prompt 构建与答案生成（真实 LLM / 离线 Mock）。

顶层**不得** import 任何第三方库；`openai` 只在 `Generator.__init__` /
`Generator.answer` 内部延迟导入，保证离线可 `import src.generate`。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.fusion import Hit

if TYPE_CHECKING:  # 仅类型检查期
    from src.config import Settings

__all__ = ["Answer", "build_prompt", "Generator", "MockGenerator", "get_generator"]

# 指令段硬要求（SPEC 5 节 build_prompt 第 1 条，逐字，不得改写）
INSTRUCTION = (
    "仅依据【资料】回答；资料中未包含的信息，必须回答「根据现有资料无法回答」；"
    "不得编造出处；回答末尾用 `[编号]` 列出实际用到的资料"
)

_HEADER = "你是严谨的文档问答助手。\n" + INSTRUCTION + "\n"

# 无资料时的占位说明（SPEC 硬要求原文）
NO_MATERIAL = "（无可用资料）"

_CITATION_RE = re.compile(r"\[(\d+)\]")

# 生成参数（SPEC：temperature=0，timeout=60，失败重试 1 次）
_TEMPERATURE = 0
_TIMEOUT = 60
_MAX_RETRIES = 1


def format_material(index: int, hit: Hit) -> str:
    """单条资料格式：`[{i}] 来源：{source} > {heading}\\n{text}`（半角冒号 + ` > ` 分隔符）。"""
    return f"[{index}] 来源：{hit.source} > {hit.heading}\n{hit.text}"


def _assemble(question: str, materials: list[str]) -> str:
    """按固定模板拼装 prompt：头部 + 问题段 + 资料段。"""
    body = "\n\n".join(materials) if materials else NO_MATERIAL
    return f"{_HEADER}\n【问题】\n{question}\n\n【资料】\n{body}\n"


def build_prompt(question: str, hits: list[Hit], max_chars: int = 3000) -> str:
    """构建问答 prompt。

    - 指令段包含 SPEC 硬要求原文；每条资料为 `[{i}] 来源：{source} > {heading}\\n{text}`，i 从 1 开始。
    - 总长超 `max_chars` 时按顺序截断，但**至少保留 1 条资料**。
    - `hits` 为空 → 仍返回合法 prompt，资料区写 `（无可用资料）`。
    """
    if not hits:
        return _assemble(question, [])

    materials = [format_material(i, hit) for i, hit in enumerate(hits, start=1)]
    prompt = _assemble(question, materials)
    if max_chars is None or max_chars <= 0 or len(prompt) <= max_chars:
        return prompt

    # 依次加资料，至少保留第 1 条（即使它单独就超限，也不裁剪模板与资料编号）
    kept = [materials[0]]
    for material in materials[1:]:
        if len(_assemble(question, kept + [material])) > max_chars:
            break
        kept.append(material)
    return _assemble(question, kept)


def extract_citations(text: str) -> list[str]:
    """正则抽出 `[数字]`，去重后按数字升序（返回字符串列表，如 ["1","3"]）。"""
    numbers = {int(match) for match in _CITATION_RE.findall(text or "")}
    return [str(n) for n in sorted(numbers)]


@dataclass
class Answer:
    text: str
    citations: list[str] = field(default_factory=list)
    latency_ms: int = 0
    prompt_chars: int = 0
    mocked: bool = False


class Generator:
    """OpenAI 兼容端点生成器；`openai` 延迟导入，temperature=0，timeout=60。"""

    def __init__(self, settings: "Settings") -> None:
        self.settings = settings
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY 未配置")
        from openai import OpenAI  # 延迟导入

        self.client = OpenAI(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key
        )

    def _complete(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=_TEMPERATURE,
            timeout=_TIMEOUT,
        )
        return resp.choices[0].message.content or ""

    def answer(self, question: str, hits: list[Hit]) -> Answer:
        prompt = build_prompt(question, hits)
        started = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                text = self._complete(prompt)
                latency_ms = int((time.perf_counter() - started) * 1000)
                return Answer(
                    text=text,
                    citations=extract_citations(text),
                    latency_ms=latency_ms,
                    prompt_chars=len(prompt),
                    mocked=False,
                )
            except Exception as exc:  # 重试 1 次后抛 RuntimeError
                last_error = exc
                if attempt >= _MAX_RETRIES:
                    break
        raise RuntimeError(f"LLM 调用失败（已重试 {_MAX_RETRIES} 次）: {last_error}")


class MockGenerator:
    """离线生成器：不联网、不读 API key，仅由输入推导（确定性）。"""

    def __init__(self, settings: "Settings") -> None:
        self.settings = settings

    def answer(self, question: str, hits: list[Hit]) -> Answer:
        started = time.perf_counter()
        prompt_chars = len(build_prompt(question, hits))
        if not hits:
            text = "根据现有资料无法回答"
            citations: list[str] = []
        else:
            # 取第一条资料的第一句作答案，并附 [1] 引用
            first = hits[0].text or ""
            sentence = re.split(r"(?<=[。！？!?；;\n])", first.strip())[0].strip()
            text = f"{sentence}[1]" if sentence else "[1]"
            citations = ["1"]
        latency_ms = int((time.perf_counter() - started) * 1000)
        return Answer(
            text=text,
            citations=citations,
            latency_ms=latency_ms,
            prompt_chars=prompt_chars,
            mocked=True,
        )


def get_generator(settings: "Settings") -> "Generator | MockGenerator":
    """`settings.mock` 为真返回 MockGenerator，否则返回 Generator。"""
    if settings.mock:
        return MockGenerator(settings)
    return Generator(settings)
