"""配置层：纯标准库读取 .env 与环境变量，产出冻结的 Settings。

约定（SPEC §5）：
- 环境变量（os.environ）优先级高于 .env 文件。
- 缺 key 用默认值兜底，不抛异常。
- 布尔解析：1/true/yes/on（忽略大小写）= True，其余 False。
- 路径字段：相对路径一律 PROJECT_ROOT / 值 解析为绝对路径。
- python-dotenv 可导入则用它读，否则用手写解析（两者结果一致）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# ==================== 路径常量 ====================

# src/config.py -> src/ -> rag-doc-qa/
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

ENV_FILE: Path = PROJECT_ROOT / ".env"

# ==================== 默认值（SPEC §3 表格） ====================

DEFAULTS: dict[str, str] = {
    # ── 生成模型（OpenAI 兼容端点）──
    "LLM_BASE_URL": "https://api.deepseek.com/v1",
    "LLM_API_KEY": "",
    "LLM_MODEL": "deepseek-chat",
    # ── Embedding ──
    "EMBED_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "EMBED_API_KEY": "",
    "EMBED_MODEL": "text-embedding-v3",
    "EMBED_DIM": "1024",
    "EMBED_BATCH": "10",
    # ── Rerank（关闭时不发任何请求）──
    "RERANK_ENABLED": "0",
    "RERANK_URL": "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
    "RERANK_MODEL": "gte-rerank-v2",
    "RERANK_API_KEY": "",
    # ── 运行模式 ──
    "MOCK": "0",
    # ── 检索后处理 ──
    # 检索结果整理模式（T-020 修订）：off / diverse / expand，默认 off（安全默认，行为=现状）
    "SECTION_MODE": "off",
    # ── 路径与检索参数 ──
    "CHROMA_DIR": "data/chroma",
    "RAW_DIR": "data/raw",
    "CHUNKS_FILE": "data/chunks.jsonl",
    "COLLECTION": "doc_qa",
    "TOP_K_VEC": "10",
    "TOP_K_BM25": "10",
    "TOP_K_FINAL": "15",
    "CHUNK_SIZE": "400",
    "CHUNK_OVERLAP": "50",
}

# 布尔解析的真值集合（忽略大小写）
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

# 检索结果整理模式的合法取值（去首尾空白 + 转小写后比较）
SECTION_MODES = ("off", "diverse", "expand")

# 整理模式的兜底值：非法值 / 空值一律回退到它，不抛异常
_SECTION_MODE_FALLBACK = "off"

# 路径型字段：相对路径需要与 PROJECT_ROOT 拼接
_PATH_FIELDS = ("CHROMA_DIR", "RAW_DIR", "CHUNKS_FILE")


# ==================== 冻结数据结构 ====================


@dataclass(frozen=True)
class Settings:
    """全部运行期配置。字段顺序与 SPEC §5 一致。"""

    llm_base_url: str
    llm_api_key: str
    llm_model: str
    embed_base_url: str
    embed_api_key: str
    embed_model: str
    embed_dim: int
    embed_batch: int
    rerank_enabled: bool
    rerank_url: str
    rerank_model: str
    rerank_api_key: str
    mock: bool
    section_mode: str
    chroma_dir: Path
    raw_dir: Path
    chunks_file: Path
    collection: str
    top_k_vec: int
    top_k_bm25: int
    top_k_final: int
    chunk_size: int
    chunk_overlap: int


# ==================== 解析工具 ====================


def parse_env_file(path: Path) -> dict[str, str]:
    """手写 .env 解析。

    规则：忽略空行与 `#` 开头的行；`KEY=VALUE` 按第一个 `=` 切分；
    值两端引号剥除（单引号与双引号均可，可跨多个字符）。
    解析失败的行直接跳过，不抛异常。
    """
    result: dict[str, str] = {}
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return result

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()
        # 剥除两端成对引号
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if not key:
            continue
        result[key] = value
    return result


def _normalize_dotenv_mapping(mapping: object) -> dict[str, str]:
    """把 python-dotenv 的返回值规整成手写解析同形的 {str: str}。"""
    normalized: dict[str, str] = {}
    if not isinstance(mapping, dict):
        return normalized
    for key, value in mapping.items():
        if value is None:
            normalized[str(key)] = ""
        else:
            normalized[str(key)] = str(value)
    return normalized


def load_env_values(env_file: Path | None = None) -> dict[str, str]:
    """合并「默认值 <- .env 文件 <- os.environ」，返回裸字符串映射。

    python-dotenv 可选：能导入就用它读，否则用手写解析；两条路径结果一致。
    """
    values: dict[str, str] = dict(DEFAULTS)

    target = ENV_FILE if env_file is None else Path(env_file)

    file_values: dict[str, str] = {}
    if target.is_file():
        try:
            from dotenv import dotenv_values  # 延迟导入：第三方库不得在模块顶层
        except Exception:
            file_values = parse_env_file(target)
        else:
            try:
                file_values = _normalize_dotenv_mapping(dotenv_values(str(target)))
            except Exception:
                file_values = parse_env_file(target)

    values.update(file_values)

    # 环境变量优先级最高（只覆盖已声明的 key 之外的新 key 也一并收集）
    for key, raw in os.environ.items():
        values[key] = raw

    return values


def _get_str(values: dict[str, str], key: str) -> str:
    return str(values.get(key, DEFAULTS.get(key, "")))


def _get_int(values: dict[str, str], key: str) -> int:
    """缺 key / 非法值都退回默认值，绝不抛异常。"""
    fallback_raw = DEFAULTS.get(key, "0")
    try:
        fallback = int(fallback_raw)
    except (TypeError, ValueError):
        fallback = 0
    raw = values.get(key)
    if raw is None:
        return fallback
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return fallback


def _get_bool(values: dict[str, str], key: str) -> bool:
    """1/true/yes/on（忽略大小写）= True，其余（含缺失、空串）False。"""
    raw = values.get(key, DEFAULTS.get(key, ""))
    if raw is None:
        return False
    return str(raw).strip().lower() in _TRUE_VALUES


def _get_section_mode(values: dict[str, str], key: str) -> str:
    """解析检索结果整理模式：去首尾空白 + 转小写，非法值 / 空值一律回退 `off`。

    与 `MOCK` / `RERANK_ENABLED` 的"缺 key 用默认值兜底，不抛异常"同一口径：
    配置写错（拼错、写中文、留空）只该退化成安全默认，不该让整个服务起不来。
    """
    raw = values.get(key, DEFAULTS.get(key, _SECTION_MODE_FALLBACK))
    if raw is None:
        return _SECTION_MODE_FALLBACK
    mode = str(raw).strip().lower()
    return mode if mode in SECTION_MODES else _SECTION_MODE_FALLBACK


def _resolve_path(value: str) -> Path:
    """相对路径一律 PROJECT_ROOT / 值，返回绝对路径。"""
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


# ==================== 冻结入口 ====================


def load_settings(env_file: Path | None = None) -> Settings:
    """读取配置并返回 Settings。任何缺失/异常都退回默认值。"""
    values = load_env_values(env_file)

    resolved: dict[str, object] = {}
    for key in DEFAULTS:
        if key in _PATH_FIELDS:
            resolved[key] = _resolve_path(_get_str(values, key))
        elif key in ("EMBED_DIM", "EMBED_BATCH", "TOP_K_VEC", "TOP_K_BM25",
                     "TOP_K_FINAL", "CHUNK_SIZE", "CHUNK_OVERLAP"):
            resolved[key] = _get_int(values, key)
        elif key in ("RERANK_ENABLED", "MOCK"):
            resolved[key] = _get_bool(values, key)
        elif key == "SECTION_MODE":
            resolved[key] = _get_section_mode(values, key)
        else:
            resolved[key] = _get_str(values, key)

    return Settings(
        llm_base_url=resolved["LLM_BASE_URL"],  # type: ignore[arg-type]
        llm_api_key=resolved["LLM_API_KEY"],  # type: ignore[arg-type]
        llm_model=resolved["LLM_MODEL"],  # type: ignore[arg-type]
        embed_base_url=resolved["EMBED_BASE_URL"],  # type: ignore[arg-type]
        embed_api_key=resolved["EMBED_API_KEY"],  # type: ignore[arg-type]
        embed_model=resolved["EMBED_MODEL"],  # type: ignore[arg-type]
        embed_dim=resolved["EMBED_DIM"],  # type: ignore[arg-type]
        embed_batch=resolved["EMBED_BATCH"],  # type: ignore[arg-type]
        rerank_enabled=resolved["RERANK_ENABLED"],  # type: ignore[arg-type]
        rerank_url=resolved["RERANK_URL"],  # type: ignore[arg-type]
        rerank_model=resolved["RERANK_MODEL"],  # type: ignore[arg-type]
        rerank_api_key=resolved["RERANK_API_KEY"],  # type: ignore[arg-type]
        mock=resolved["MOCK"],  # type: ignore[arg-type]
        section_mode=resolved["SECTION_MODE"],  # type: ignore[arg-type]
        chroma_dir=resolved["CHROMA_DIR"],  # type: ignore[arg-type]
        raw_dir=resolved["RAW_DIR"],  # type: ignore[arg-type]
        chunks_file=resolved["CHUNKS_FILE"],  # type: ignore[arg-type]
        collection=resolved["COLLECTION"],  # type: ignore[arg-type]
        top_k_vec=resolved["TOP_K_VEC"],  # type: ignore[arg-type]
        top_k_bm25=resolved["TOP_K_BM25"],  # type: ignore[arg-type]
        top_k_final=resolved["TOP_K_FINAL"],  # type: ignore[arg-type]
        chunk_size=resolved["CHUNK_SIZE"],  # type: ignore[arg-type]
        chunk_overlap=resolved["CHUNK_OVERLAP"],  # type: ignore[arg-type]
    )
