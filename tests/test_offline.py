"""离线单测：只依赖标准库 + src.config / src.chunking / src.fusion / src.embed / src.ingest / eval.metrics。

覆盖 SPEC.md 332-339 要求的 6 类契约。运行方式见 SPEC.md §6：
    & $P -m unittest discover -s "$R\\tests" -t $R -v
"""

from __future__ import annotations

import contextlib
import dataclasses
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.config as config  # noqa: E402
from src.chunking import Chunk, split_text  # noqa: E402
from src.embed import MockEmbedder, get_embedder  # noqa: E402
from src.fusion import Hit, dedupe_keep_order, rrf_fuse  # noqa: E402
from src.ingest import read_raw_files  # noqa: E402
from src.retrieve import dedupe_by_section, expand_to_sections  # noqa: E402  # 顶层无第三方库，可离线导入

from eval.metrics import (  # noqa: E402
    aggregate,
    hit_at_k,
    keypoints_match,
    normalize_answer,
    score_answer,
)

# eval.run_eval 也可以离线导入：它的第三方库（chromadb / openai）全部在**函数内延迟导入**，
# 模块顶层只有标准库 + 项目内模块（实测 import 后 sys.modules 里 0 个第三方库），
# 因此不违反 AGENTS.md §6「tests/test_offline.py 不得 import chromadb / openai / ...」。
from eval.run_eval import (  # noqa: E402
    RECORD_FIELDS,
    SUMMARY_FIELDS,
    run_once,
    summarize,
)

# 全角与半角标点样本（SPEC 304 列出的字符集合）
FULLWIDTH_PUNCT = "，。、；：？！,.;:?!()（）[]【】\"'`"

#: load_settings 会读取的环境变量名：由 Settings 字段自动推导，避免加配置项后漏隔离
SETTINGS_ENV_KEYS: tuple[str, ...] = tuple(f.name.upper() for f in dataclasses.fields(config.Settings))


@contextlib.contextmanager
def isolate_settings_env() -> Iterator[None]:
    """临时移除调用者环境里全部 Settings 相关变量，退出时原样还原。

    必须真删键而不是置空串：`load_settings` 会把 `os.environ` 的每一项都当作
    覆盖值，置空串同样会盖掉 `.env`（空串不是"未设置"）。

    SPEC §5 规定环境变量优先级高于 `.env`，所以「想在 `.env` 里造数据」的用例
    必须先挡住调用者 shell 里残留的 `MOCK` / `CHUNK_SIZE` 等键，否则会看到假失败
    （PLAN T-013：README 快速开始第 1 步就教用户 `$env:MOCK = "1"`）。
    """
    saved: dict[str, str] = {key: os.environ[key] for key in SETTINGS_ENV_KEYS if key in os.environ}
    for key in saved:
        del os.environ[key]
    try:
        yield
    finally:
        os.environ.update(saved)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ==================== 1. src.chunking.split_text ====================


class SplitTextTests(unittest.TestCase):
    def test_empty_or_whitespace_returns_empty_list(self) -> None:
        self.assertEqual(split_text("", "d.md"), [])
        self.assertEqual(split_text("   \n\n\t  \r\n ", "d.md"), [])

    def test_small_doc_single_chunk_with_id_and_heading(self) -> None:
        chunks = split_text("# 标题甲\n\n只有一个短段落。", "d.md", size=400, overlap=50)
        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]
        self.assertEqual(chunk.id, "d.md#0000")
        self.assertEqual(chunk.index, 0)
        self.assertEqual(chunk.source, "d.md")
        self.assertEqual(chunk.heading, "标题甲")
        self.assertIn("只有一个短段落", chunk.text)

    def test_long_doc_chunk_size_bound_ids_continuous_and_covers_paragraphs(self) -> None:
        paragraphs = [
            "检索增强生成系统通常由文档切块、向量化、检索与生成四个阶段组成，每个阶段都会影响最终答案的质量。",
            "文档切块阶段需要权衡块大小与重叠长度，块过大会引入无关上下文，块过小则会割裂语义完整性。",
            "向量化阶段把文本映射到高维空间，同义表达的向量距离应当明显小于无关文本之间的距离。",
            "生成阶段把检索结果拼接进提示词，并强制模型在证据不足时明确表示无法回答该问题。",
        ]
        source = "guide.md"
        size, overlap = 100, 20
        chunks = split_text("\n\n".join(paragraphs), source, size=size, overlap=overlap)

        self.assertGreater(len(chunks), 1)
        for i, chunk in enumerate(chunks):
            self.assertEqual(chunk.id, f"{source}#{i:04d}")
            self.assertEqual(chunk.index, i)
            self.assertTrue(chunk.text.strip(), "chunk 文本必须非空")
            self.assertLessEqual(len(chunk.text), size + overlap)
        self.assertEqual(chunks[0].heading, "")

        joined = "".join(chunk.text for chunk in chunks)
        for paragraph in paragraphs:
            self.assertIn(paragraph, joined)

    def test_heading_is_hard_boundary_without_cross_boundary_overlap(self) -> None:
        body_a = "甲节正文内容一二三四五六七八九十"
        body_b = "乙节正文内容甲乙丙丁戊己庚辛壬癸"
        text = f"# 甲\n\n{body_a}\n\n# 乙\n\n{body_b}\n"
        size, overlap = 50, 10
        chunks = split_text(text, "h.md", size=size, overlap=overlap)

        self.assertEqual([chunk.heading for chunk in chunks], ["甲", "乙"])
        first, second = chunks[0], chunks[1]
        self.assertNotIn("#", first.heading)
        self.assertIn(body_a, first.text)
        self.assertIn(body_b, second.text)
        # 跨标题边界不得出现重叠前缀
        self.assertFalse(second.text.startswith(first.text[-overlap:]))

    def test_split_text_is_deterministic(self) -> None:
        text = "# 甲\n\n" + "段落文本。" * 40 + "\n\n# 乙\n\n" + "另一个段落。" * 40
        first = split_text(text, "s.md", size=120, overlap=30)
        second = split_text(text, "s.md", size=120, overlap=30)
        self.assertEqual(
            [(c.id, c.text, c.heading, c.index) for c in first],
            [(c.id, c.text, c.heading, c.index) for c in second],
        )


# ==================== 2. src.fusion ====================


class FusionTests(unittest.TestCase):
    def test_rrf_fuse_hand_computed_two_retrievers_order(self) -> None:
        k = 60
        rankings = {"vector": ["c1", "c2", "c3"], "bm25": ["c3", "c1", "c2"]}
        fused = rrf_fuse(rankings, k=k)
        # 手算：c1 = 1/61+1/62；c3 = 1/63+1/61；c2 = 1/62+1/63
        self.assertEqual([chunk_id for chunk_id, _ in fused], ["c1", "c3", "c2"])
        expected = {
            "c1": 1 / 61 + 1 / 62,
            "c3": 1 / 63 + 1 / 61,
            "c2": 1 / 62 + 1 / 63,
        }
        for chunk_id, score in fused:
            self.assertAlmostEqual(score, expected[chunk_id], places=12)

    def test_rrf_fuse_equal_score_breaks_tie_by_id_ascending(self) -> None:
        fused = rrf_fuse({"r1": ["b"], "r2": ["a"]}, k=60)
        self.assertEqual([chunk_id for chunk_id, _ in fused], ["a", "b"])
        self.assertAlmostEqual(fused[0][1], fused[1][1], places=12)

    def test_rrf_fuse_empty_and_duplicate_ids_count_first_rank_only(self) -> None:
        self.assertEqual(rrf_fuse({}), [])
        self.assertEqual(rrf_fuse({"vector": []}), [])
        fused = rrf_fuse({"vector": ["x", "x", "y"]}, k=60)
        self.assertEqual([chunk_id for chunk_id, _ in fused], ["x", "y"])
        self.assertAlmostEqual(fused[0][1], 1 / 61, places=12)
        self.assertAlmostEqual(fused[1][1], 1 / 62, places=12)

    def test_rrf_fuse_default_k_is_60(self) -> None:
        """省略 k 时必须等价于 SPEC §5 规定的 k=60（生产路径 src/retrieve.py 正是走默认值）。

        本用例刻意不传 k，直接锁死默认值 60：若默认值被改成 1，得分会变成 1/2 而非 1/61。
        """
        single = rrf_fuse({"vector": ["a"]})
        self.assertEqual([chunk_id for chunk_id, _ in single], ["a"])
        self.assertAlmostEqual(single[0][1], 1.0 / 61, places=12)
        self.assertEqual(rrf_fuse({"vector": ["a"]}), rrf_fuse({"vector": ["a"]}, k=60))
        self.assertNotAlmostEqual(single[0][1], 1.0 / 2, places=12)

    def test_dedupe_keep_order(self) -> None:
        self.assertEqual(dedupe_keep_order(["a", "b", "a"]), ["a", "b"])
        self.assertEqual(dedupe_keep_order([]), [])
        self.assertEqual(dedupe_keep_order(["b", "b", "a", "b"]), ["b", "a"])


# ==================== 3. eval.metrics ====================


class MetricsNormalizeTests(unittest.TestCase):
    def test_normalize_answer_fullwidth_punct_and_case(self) -> None:
        self.assertEqual(normalize_answer("ＡＢＣ，ＤＥＦ。"), "abcdef")
        self.assertEqual(normalize_answer("  Hello, World! "), "helloworld")
        self.assertEqual(normalize_answer("（测试）【一】'二'"), "测试一二")
        for char in FULLWIDTH_PUNCT:
            self.assertEqual(normalize_answer(f"甲{char}乙"), "甲乙", f"标点未去除: {char!r}")
        self.assertEqual(normalize_answer("  \n\t "), "")

    def test_keypoints_match_ratio(self) -> None:
        pred = "北京是中国的首都，人口超过两千万。"
        self.assertAlmostEqual(keypoints_match(pred, ["北京", "首都", "上海"]), 2 / 3, places=6)
        self.assertEqual(keypoints_match(pred, ["北京", "首都"]), 1.0)
        self.assertEqual(keypoints_match(pred, ["上海"]), 0.0)
        self.assertEqual(keypoints_match(pred, []), 0.0)
        # 归一化后为空的关键点不计入分母
        self.assertEqual(keypoints_match(pred, ["，。"]), 0.0)

    def test_score_answer_all_branches(self) -> None:
        # must_refuse=True：命中拒答关键词
        self.assertEqual(score_answer("资料中未提及相关内容。", "", [], True), "correct")
        self.assertEqual(score_answer("无法回答该问题", "", [], True), "correct")
        # must_refuse=True：未拒答
        self.assertEqual(score_answer("北京是中国的首都。", "", [], True), "wrong")
        # 非拒答 + keypoints 命中率 >= 0.8
        self.assertEqual(
            score_answer("北京是中国的首都，人口很多。", "北京", ["北京", "首都", "人口"], False),
            "correct",
        )
        # 非拒答 + 命中一部分 -> partial
        self.assertEqual(score_answer("北京是中国的首都。", "", ["北京", "首都", "上海"], False), "partial")
        # exact_match 分支（keypoints 为空，只能靠 exact_match）
        self.assertEqual(score_answer("北京", "北京", [], False), "correct")
        # 完全无关 -> wrong
        self.assertEqual(score_answer("完全无关的回答", "北京的", ["上海"], False), "wrong")

    def test_hit_at_k_boundaries(self) -> None:
        retrieved = ["a.md#0000", "b.pdf#0001"]
        self.assertTrue(hit_at_k(retrieved, ["a.md"], 1))
        self.assertTrue(hit_at_k(retrieved, ["b.pdf"], 2))
        self.assertFalse(hit_at_k(retrieved, ["c.md"], 2))
        self.assertFalse(hit_at_k(retrieved, ["b.pdf"], 1))
        self.assertFalse(hit_at_k(retrieved, ["a.md"], 0))
        self.assertFalse(hit_at_k(retrieved, ["a.md"], -1))
        self.assertTrue(hit_at_k(retrieved, ["a.md"], 99))
        self.assertFalse(hit_at_k(retrieved, [], 5))
        self.assertFalse(hit_at_k([], ["a.md"], 5))

    def test_aggregate_division_by_zero_and_rates(self) -> None:
        empty = aggregate([])
        self.assertEqual(empty["n"], 0)
        for key in ("accuracy", "partial_rate", "wrong_rate", "refusal_accuracy", "hit_rate"):
            self.assertEqual(empty[key], 0.0)

        records = [
            {"score": "correct", "hit": True, "must_refuse": False},
            {"score": "partial", "hit": False},
            {"score": "wrong", "hit": True, "must_refuse": False},
        ]
        stats = aggregate(records)
        self.assertEqual(stats["n"], 3)
        self.assertAlmostEqual(stats["accuracy"], 1 / 3, places=6)
        self.assertAlmostEqual(stats["partial_rate"], 1 / 3, places=6)
        self.assertAlmostEqual(stats["wrong_rate"], 1 / 3, places=6)
        self.assertAlmostEqual(stats["hit_rate"], 2 / 3, places=6)
        # 没有拒答题 -> 除零保护
        self.assertEqual(stats["refusal_accuracy"], 0.0)

        refusal_records = [
            {"score": "correct", "hit": False, "must_refuse": True},
            {"score": "wrong", "hit": False, "must_refuse": True},
        ]
        refusal_stats = aggregate(refusal_records)
        self.assertEqual(refusal_stats["n"], 2)
        self.assertAlmostEqual(refusal_stats["refusal_accuracy"], 0.5, places=6)


# ==================== 4. src.config.load_settings ====================


class LoadSettingsTests(unittest.TestCase):
    """SPEC §5：环境变量优先级高于 .env，所以本类必须自己隔离进程环境。

    否则调用者 shell 里残留的 MOCK / CHUNK_SIZE（例如 README 快速开始第 1 步
    教的 `$env:MOCK = "1"`）会按契约覆盖 .env，让断言看到假失败（PLAN T-013）。
    """

    #: load_settings 会读取的环境变量名：由 Settings 字段自动推导，避免漏项
    ENV_KEYS: tuple[str, ...] = SETTINGS_ENV_KEYS

    def _isolated_env(self) -> Iterator[None]:
        """临时移除调用者环境里全部 Settings 相关变量，退出时原样还原。"""
        return isolate_settings_env()

    def _write_env(self, content: str) -> Path:
        tmp_dir = Path(tempfile.mkdtemp(prefix="rag_env_"))
        env_file = tmp_dir / "test.env"
        env_file.write_text(content, encoding="utf-8")
        return env_file

    def test_env_file_overrides_defaults_with_int_and_bool(self) -> None:
        with self._isolated_env():
            env_file = self._write_env(
                "\n".join(
                    [
                        "# 注释行",
                        "",
                        "LLM_MODEL=offline-test-model",
                        "EMBED_DIM=48",
                        "EMBED_BATCH=3",
                        "CHUNK_SIZE=123",
                        "CHUNK_OVERLAP=7",
                        "MOCK=1",
                        "RERANK_ENABLED=no",
                        "COLLECTION=offline_doc_qa",
                    ]
                )
                + "\n"
            )
            settings = config.load_settings(env_file=env_file)

            self.assertEqual(settings.llm_model, "offline-test-model")
            self.assertEqual(settings.collection, "offline_doc_qa")
            self.assertIsInstance(settings.embed_dim, int)
            self.assertEqual(settings.embed_dim, 48)
            self.assertEqual(settings.embed_batch, 3)
            self.assertEqual(settings.chunk_size, 123)
            self.assertEqual(settings.chunk_overlap, 7)
            self.assertIs(settings.mock, True)
            self.assertIs(settings.rerank_enabled, False)
            # 未在 .env 中声明的 key 使用默认兜底值
            # 15 是 SPEC.md:103 的契约默认值（T-028 Step 4 由 4 改为 15）；
            # 断言跟着契约走，不是放宽校验：数值一变这里就必须失败。
            self.assertEqual(settings.top_k_final, 15)

    def test_relative_paths_resolve_to_absolute_under_project_root(self) -> None:
        with self._isolated_env():
            env_file = self._write_env(
                "CHROMA_DIR=data/chroma_offline\nRAW_DIR=data/raw_offline\nCHUNKS_FILE=data/chunks_offline.jsonl\n"
            )
            settings = config.load_settings(env_file=env_file)

            expected_chroma = (config.PROJECT_ROOT / "data/chroma_offline").resolve()
            self.assertTrue(settings.chroma_dir.is_absolute())
            self.assertEqual(settings.chroma_dir, expected_chroma)
            self.assertTrue(settings.raw_dir.is_absolute())
            self.assertTrue(settings.chunks_file.is_absolute())
            self.assertEqual(settings.raw_dir, (config.PROJECT_ROOT / "data/raw_offline").resolve())
            self.assertEqual(settings.chunks_file, (config.PROJECT_ROOT / "data/chunks_offline.jsonl").resolve())

    def test_bool_variants_and_missing_env_file_do_not_raise(self) -> None:
        with self._isolated_env():
            for raw, expected in [("on", True), ("YES", True), ("True", True), ("0", False), ("maybe", False)]:
                env_file = self._write_env(f"MOCK={raw}\n")
                self.assertIs(config.load_settings(env_file=env_file).mock, expected, raw)

            missing = Path(tempfile.mkdtemp(prefix="rag_env_missing_")) / "nope.env"
            settings = config.load_settings(env_file=missing)
            self.assertIsInstance(settings, config.Settings)
            self.assertIsInstance(settings.embed_dim, int)
            self.assertTrue(settings.chunks_file.is_absolute())


# ==================== 5. src.embed.MockEmbedder ====================


class MockEmbedderTests(unittest.TestCase):
    def setUp(self) -> None:
        # 维度等配置同样来自 load_settings，必须与调用者环境隔离（PLAN T-013）
        isolated = isolate_settings_env()
        isolated.__enter__()
        self.addCleanup(isolated.__exit__, None, None, None)
        self.settings = config.load_settings()
        self.embedder = MockEmbedder(self.settings)

    def test_identical_input_is_deterministic_and_dimension_matches(self) -> None:
        text = "检索增强生成把文档切块后向量化"
        vec = self.embedder.embed_query(text)
        self.assertEqual(len(vec), self.settings.embed_dim)
        self.assertEqual(vec, self.embedder.embed_query(text))
        batch = self.embedder.embed_texts([text, text])
        self.assertEqual(batch[0], batch[1])
        self.assertEqual(batch[0], vec)

    def test_vector_is_not_all_zero(self) -> None:
        for text in ["检索增强生成", "   ", ""]:
            vec = self.embedder.embed_query(text)
            self.assertEqual(len(vec), self.settings.embed_dim)
            self.assertNotEqual(sum(abs(value) for value in vec), 0.0, f"全零向量: {text!r}")

    def test_shared_words_have_higher_cosine_than_unrelated(self) -> None:
        base = "检索增强生成系统把文档切块后向量化并写入索引"
        similar = "检索增强生成系统把文档切块后向量化并写入向量索引"
        unrelated = "今天天气不错适合出门散步并且阳光很好"
        vec_base = self.embedder.embed_query(base)
        vec_similar = self.embedder.embed_query(similar)
        vec_unrelated = self.embedder.embed_query(unrelated)
        self.assertGreater(_cosine(vec_base, vec_similar), _cosine(vec_base, vec_unrelated))

    def test_empty_batch_and_get_embedder_mock_mode(self) -> None:
        self.assertEqual(self.embedder.embed_texts([]), [])
        mock_settings = dataclasses.replace(self.settings, mock=True)
        self.assertIsInstance(get_embedder(mock_settings), MockEmbedder)


# ==================== 6. Chunk 序列化往返 ====================


class ChunkRoundTripTests(unittest.TestCase):
    def test_to_dict_from_dict_round_trip(self) -> None:
        chunk = Chunk(id="doc.md#0001", text="段落文本", source="doc.md", heading="标题甲", index=1)
        payload = chunk.to_dict()
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["id"], "doc.md#0001")
        self.assertEqual(payload["index"], 1)
        self.assertEqual(Chunk.from_dict(payload), chunk)

        empty_heading = Chunk(id="doc.md#0000", text="无标题段落", source="doc.md", heading="", index=0)
        self.assertEqual(Chunk.from_dict(empty_heading.to_dict()), empty_heading)
        self.assertEqual(
            (Chunk.from_dict(empty_heading.to_dict()).text, Chunk.from_dict(empty_heading.to_dict()).heading),
            ("无标题段落", ""),
        )


# ==================== 7. src.ingest.read_raw_files 语料过滤 ====================


class ReadRawFilesTests(unittest.TestCase):
    """README 是给人读的语料格式说明书，不是知识，不得被切块入库（PLAN T-012）。"""

    def _make_raw_dir(self) -> Path:
        return Path(tempfile.mkdtemp(prefix="rag_raw_"))

    def test_readme_is_skipped_but_normal_corpus_is_read(self) -> None:
        raw_dir = self._make_raw_dir()
        (raw_dir / "README.md").write_text("# 语料格式说明\n\n请把 .md 放进本目录。\n", encoding="utf-8")
        (raw_dir / "01_知识.md").write_text("# 真实知识\n\n这是应当被入库的正文段落。\n", encoding="utf-8")

        docs = read_raw_files(raw_dir)

        self.assertEqual([doc.source for doc in docs], ["01_知识.md"])
        self.assertNotIn("README.md", [doc.source for doc in docs])

    def test_readme_uppercase_extension_is_skipped_too(self) -> None:
        raw_dir = self._make_raw_dir()
        (raw_dir / "README.MD").write_text("# 语料格式说明\n\n请把 .md 放进本目录。\n", encoding="utf-8")
        (raw_dir / "02_知识.md").write_text("# 真实知识\n\n这是应当被入库的正文段落。\n", encoding="utf-8")

        docs = read_raw_files(raw_dir)

        self.assertEqual([doc.source for doc in docs], ["02_知识.md"])


# ==================== 8. 连续 keypoint 覆盖率接入评测报告（T-019） ====================


class _StubRetriever:
    """`run_once` 只用到 `search(text, top_k)`；桩对象让本节用例完全不碰 chromadb。"""

    def __init__(self, chunk_ids: list[str]) -> None:
        self._chunk_ids = chunk_ids

    def search(self, text: str, top_k: int) -> list[SimpleNamespace]:
        return [SimpleNamespace(chunk_id=cid) for cid in self._chunk_ids[:top_k]]


class _StubAnswer:
    def __init__(self, text: str, citations: list[str]) -> None:
        self.text = text
        self.citations = citations


class _StubGenerator:
    def __init__(self, text: str) -> None:
        self._text = text

    def answer(self, text: str, hits: list[SimpleNamespace]) -> _StubAnswer:
        return _StubAnswer(self._text, ["1"])


class KeypointCoverageReportTests(unittest.TestCase):
    """T-019：把**连续** keypoint 覆盖率接进评测报告。

    动机（`docs/EXPERIMENTS.md` E-02）：桶指标（对 / 部分对 / 错，阈值 0.8）把
    「覆盖率 0.450 → 0.550、逐题 5 升 0 降」压成了"一分未动"，读出了**相反**的结论。
    所以覆盖率必须由报告本身给出，而不是每次靠临时脚本回读逐题明细。
    本节锁三件事：① `run_once` 新增键且取值就是 `keypoints_match`；
    ② `aggregate` 把拒答题排除在 `avg_keypoint_coverage` 之外、无记录时给 0.0；
    ③ 既有 7 个汇总字段仍在、语义未变。
    """

    def setUp(self) -> None:
        # load_settings 会读环境变量，必须与调用者 shell 隔离（PLAN T-013）
        isolated = isolate_settings_env()
        isolated.__enter__()
        self.addCleanup(isolated.__exit__, None, None, None)
        self.settings = config.load_settings()

    def _question(self, **overrides: object) -> dict:
        question: dict = {
            "id": "q-test",
            "type": "single_hop",
            "question": "中国的首都是哪里",
            "gold": "北京",
            "keypoints": ["北京", "首都", "上海"],
            "gold_sources": ["a.md"],
            "must_refuse": False,
        }
        question.update(overrides)
        return question

    # —— 冻结接口 1：run_once 新增 keypoint_coverage ——

    def test_run_once_keypoint_coverage_equals_keypoints_match(self) -> None:
        """新键必须是 `keypoints_match(pred, keypoints)` 本身，而不是另一把尺子。"""
        question = self._question()
        pred = "北京是中国的首都。"
        record = run_once(
            self.settings,
            question,
            "mock",
            _StubRetriever(["a.md#0000"]),
            _StubGenerator(pred),
            4,
        )
        self.assertAlmostEqual(record["keypoint_coverage"], 2 / 3, places=12)
        self.assertEqual(
            record["keypoint_coverage"], keypoints_match(pred, question["keypoints"])
        )
        # 覆盖率是浮点、落在 0~1
        self.assertIsInstance(record["keypoint_coverage"], float)
        self.assertGreaterEqual(record["keypoint_coverage"], 0.0)
        self.assertLessEqual(record["keypoint_coverage"], 1.0)
        # 顺带锁住「桶」的口径没变：score 仍由 score_answer 用同一批入参算出
        self.assertEqual(
            record["score"], score_answer(pred, question["gold"], question["keypoints"], False)
        )
        self.assertEqual(record["score"], "partial")

        # 拒答题：keypoints 为空 → 覆盖率 0.0（aggregate 会把它排除在均值外）
        refusal = run_once(
            self.settings,
            self._question(id="q-refuse", type="unanswerable", keypoints=[], must_refuse=True),
            "mock",
            _StubRetriever(["a.md#0000"]),
            _StubGenerator("资料中未提及相关内容。"),
            4,
        )
        self.assertEqual(refusal["keypoint_coverage"], 0.0)
        self.assertEqual(refusal["score"], "correct")

    def test_run_once_record_keys_are_frozen_plus_coverage(self) -> None:
        """既有 11 个记录键一个都没少，新键只追加在末尾（构造顺序 = 声明顺序）。"""
        record = run_once(
            self.settings,
            self._question(),
            "retrieval",
            _StubRetriever([]),
            None,
            4,
        )
        self.assertEqual(tuple(record), RECORD_FIELDS)
        for key in (
            "id",
            "type",
            "question",
            "pred",
            "gold",
            "must_refuse",
            "score",
            "retrieved_ids",
            "hit",
            "citation_hit",
            "latency_ms",
        ):
            self.assertIn(key, record)
        self.assertIn("keypoint_coverage", record)

    # —— 冻结接口 2：aggregate 新增 avg_keypoint_coverage ——

    def test_aggregate_avg_keypoint_coverage_excludes_refusal_records(self) -> None:
        records = [
            {"score": "correct", "hit": True, "must_refuse": False, "keypoint_coverage": 0.8},
            {"score": "partial", "hit": False, "must_refuse": False, "keypoint_coverage": 0.5},
            {"score": "correct", "hit": False, "must_refuse": True, "keypoint_coverage": 0.0},
        ]
        stats = aggregate(records)

        # 拒答题（must_refuse=True）被排除：只对 0.8 / 0.5 求平均
        self.assertAlmostEqual(stats["avg_keypoint_coverage"], 0.65, places=12)
        # 若把拒答题也算进去会得到 0.4333…，本断言锁死"不算进去"
        self.assertNotAlmostEqual(stats["avg_keypoint_coverage"], 1.3 / 3, places=6)
        # 与 refusal_accuracy 同一口径：缺 must_refuse 键但 type=unanswerable 也排除
        with_fallback = records + [{"score": "wrong", "type": "unanswerable", "keypoint_coverage": 1.0}]
        self.assertAlmostEqual(
            aggregate(with_fallback)["avg_keypoint_coverage"], 0.65, places=12
        )
        # 既有指标语义未变（同一批 records 上照旧）
        self.assertEqual(stats["n"], 3)
        self.assertAlmostEqual(stats["accuracy"], 2 / 3, places=6)
        self.assertAlmostEqual(stats["partial_rate"], 1 / 3, places=6)
        self.assertEqual(stats["wrong_rate"], 0.0)
        self.assertAlmostEqual(stats["hit_rate"], 1 / 3, places=6)
        self.assertAlmostEqual(stats["refusal_accuracy"], 1.0, places=6)

    def test_aggregate_avg_keypoint_coverage_zero_without_answerable_records(self) -> None:
        """没有可参与求平均的记录 → 0.0（空列表、全是拒答题两种情形）。"""
        empty = aggregate([])
        self.assertEqual(empty["n"], 0)
        self.assertEqual(empty["avg_keypoint_coverage"], 0.0)
        self.assertIsInstance(empty["avg_keypoint_coverage"], float)

        refusal_only = [
            {"score": "correct", "hit": False, "must_refuse": True, "keypoint_coverage": 0.0},
            {"score": "wrong", "hit": False, "type": "unanswerable", "keypoint_coverage": 0.9},
        ]
        stats = aggregate(refusal_only)
        self.assertEqual(stats["n"], 2)
        self.assertEqual(stats["avg_keypoint_coverage"], 0.0)
        self.assertIsInstance(stats["avg_keypoint_coverage"], float)

    def test_aggregate_skips_records_without_numeric_coverage(self) -> None:
        """缺键 / None / 非数值 → 不进分子也不进分母（**不当作 0.0**）。

        把"没测到"读成"覆盖率为零"会让均值无声偏小 —— 那正是 E-02 要避免的静默误读。
        """
        records = [
            {"score": "partial", "hit": False, "must_refuse": False, "keypoint_coverage": 0.25},
            {"score": "partial", "hit": False, "must_refuse": False},
            {"score": "partial", "hit": False, "must_refuse": False, "keypoint_coverage": None},
            {"score": "partial", "hit": False, "must_refuse": False, "keypoint_coverage": "0.9"},
        ]
        stats = aggregate(records)
        self.assertAlmostEqual(stats["avg_keypoint_coverage"], 0.25, places=12)
        self.assertNotAlmostEqual(stats["avg_keypoint_coverage"], 0.0625, places=6)
        self.assertEqual(stats["n"], 4)

    # —— 冻结接口 3：SUMMARY_FIELDS 追加字段，既有 7 键不变 ——

    def test_summary_fields_frozen_seven_keys_plus_coverage(self) -> None:
        """`summarize` 输出的 7 个既有字段名 / 顺序 / 语义不变，新字段追加在末尾。"""
        self.assertEqual(
            SUMMARY_FIELDS,
            (
                "n",
                "accuracy",
                "partial_rate",
                "wrong_rate",
                "refusal_accuracy",
                "hit_rate",
                "avg_latency_ms",
                "avg_keypoint_coverage",
            ),
        )

        records = [
            {
                "score": "correct",
                "hit": True,
                "must_refuse": False,
                "keypoint_coverage": 1.0,
                "latency_ms": 100,
            },
            {
                "score": "partial",
                "hit": False,
                "must_refuse": False,
                "keypoint_coverage": 0.5,
                "latency_ms": 200,
            },
            {
                "score": "correct",
                "hit": False,
                "must_refuse": True,
                "keypoint_coverage": 0.0,
                "latency_ms": 300,
            },
        ]
        summary = summarize(records)

        # 键集合与顺序 = 冻结清单（改名 / 删键 / 换序都会在这里失败）
        self.assertEqual(tuple(summary), SUMMARY_FIELDS)

        # 原有 7 键语义未变
        self.assertEqual(summary["n"], 3)
        self.assertAlmostEqual(summary["accuracy"], 2 / 3, places=6)
        self.assertAlmostEqual(summary["partial_rate"], 1 / 3, places=6)
        self.assertEqual(summary["wrong_rate"], 0.0)
        self.assertAlmostEqual(summary["refusal_accuracy"], 1.0, places=6)
        self.assertAlmostEqual(summary["hit_rate"], 1 / 3, places=6)
        self.assertAlmostEqual(summary["avg_latency_ms"], 200.0, places=6)

        # 新增键：0~1 的浮点，只对非拒答记录求平均
        self.assertIsInstance(summary["avg_keypoint_coverage"], float)
        self.assertAlmostEqual(summary["avg_keypoint_coverage"], 0.75, places=12)
        self.assertEqual(
            summary["avg_keypoint_coverage"], aggregate(records)["avg_keypoint_coverage"]
        )


# ==================== 9. 小节级上下文（T-020 / EXPERIMENTS E-02） ====================


def _make_chunk(chunk_id: str, text: str, source: str, heading: str, index: int) -> Chunk:
    """本节的测试夹具：chunk_id 与 source / index 一致，避免手写 id 时写错前缀。"""
    return Chunk(id=chunk_id, text=text, source=source, heading=heading, index=index)


class ExpandToSectionsTests(unittest.TestCase):
    """E-02：失分不是文件级召回不够，而是「检索到同一文件的错误小节」——所以命中一个块时
    要把它所在的**整个小节**给模型，并按小节去重。

    本节锁死的边界：① 同小节多条 hit 去重成一条且 `text` 是组内全部块按 index 拼接；
    ② 不同小节各自保留；③ 缺 id 的 hit 原样保留；④ 空输入 → `[]`；⑤ 保持首次出现顺序；
    ⑥ `chunk_id` 必须是**首次命中**的那个 chunk 的 id（`hit_at_k` 靠它前缀匹配 `gold_sources`，
    改成小节 id 会静默破坏全部历史指标的可比性）。

    ⚠️ T-020 修订：本函数只服务 `SECTION_MODE=expand` 一种模式（故保留不变）；
    `diverse`（只去重、不扩展 `text`）见 `DedupeBySectionTests`。
    """

    def test_same_section_hits_dedupe_to_first_with_whole_section_text(self) -> None:
        chunk_map = {
            "04.md#0000": _make_chunk("04.md#0000", "## 计算属性缓存 vs 方法", "04.md", "计算属性缓存 vs 方法", 0),
            "04.md#0001": _make_chunk("04.md#0001", "方法调用总会重新执行函数。", "04.md", "计算属性缓存 vs 方法", 1),
            "04.md#0002": _make_chunk("04.md#0002", "计算属性基于依赖缓存。", "04.md", "计算属性缓存 vs 方法", 2),
        }
        hits = [
            Hit("04.md#0001", "方法调用总会重新执行函数。", "04.md", "计算属性缓存 vs 方法", 0.5, "fused"),
            Hit("04.md#0002", "计算属性基于依赖缓存。", "04.md", "计算属性缓存 vs 方法", 0.4, "fused"),
        ]
        out = expand_to_sections(hits, chunk_map)

        self.assertEqual(len(out), 1)
        # 小节全文：同 source + 同 heading 的全部块按 index 升序、`\n\n` 连接
        self.assertEqual(
            out[0].text,
            "## 计算属性缓存 vs 方法\n\n方法调用总会重新执行函数。\n\n计算属性基于依赖缓存。",
        )
        # chunk_id 仍是首次命中的那个块，不是小节 id、也不是后面的块
        self.assertEqual(out[0].chunk_id, "04.md#0001")
        self.assertEqual(out[0].score, 0.5)
        self.assertEqual(out[0].retriever, "fused")
        self.assertEqual(out[0].source, "04.md")
        self.assertEqual(out[0].heading, "计算属性缓存 vs 方法")

    def test_different_sections_are_kept_separately(self) -> None:
        chunk_map = {
            "02.md#0000": _make_chunk("02.md#0000", "reactive 的局限性一。", "02.md", "reactive() 的局限性", 0),
            "02.md#0001": _make_chunk("02.md#0001", "数组注意事项。", "02.md", "数组和集合的注意事项", 1),
        }
        hits = [
            Hit("02.md#0000", "reactive 的局限性一。", "02.md", "reactive() 的局限性", 0.3, "fused"),
            Hit("02.md#0001", "数组注意事项。", "02.md", "数组和集合的注意事项", 0.2, "fused"),
        ]
        out = expand_to_sections(hits, chunk_map)

        self.assertEqual([hit.chunk_id for hit in out], ["02.md#0000", "02.md#0001"])
        self.assertEqual([hit.heading for hit in out], ["reactive() 的局限性", "数组和集合的注意事项"])
        self.assertEqual([hit.text for hit in out], ["reactive 的局限性一。", "数组注意事项。"])

    def test_same_heading_in_different_sources_are_not_deduped(self) -> None:
        """去重键是 `(source, heading)`：不同文件的同名小节互不影响。"""
        chunk_map = {
            "a.md#0000": _make_chunk("a.md#0000", "甲的安装说明。", "a.md", "安装", 0),
            "b.md#0000": _make_chunk("b.md#0000", "乙的安装说明。", "b.md", "安装", 0),
        }
        hits = [
            Hit("a.md#0000", "甲的安装说明。", "a.md", "安装", 0.9, "fused"),
            Hit("b.md#0000", "乙的安装说明。", "b.md", "安装", 0.8, "fused"),
        ]
        out = expand_to_sections(hits, chunk_map)

        self.assertEqual([hit.chunk_id for hit in out], ["a.md#0000", "b.md#0000"])

    def test_hit_missing_from_chunk_map_is_kept_unchanged(self) -> None:
        """chunk_map 里找不到 id → 原样保留（不丢、不报错、不扩展）。"""
        chunk_map = {
            "k.md#0000": _make_chunk("k.md#0000", "已入库的小节正文。", "k.md", "小节甲", 0),
        }
        orphan = Hit("gone.md#0009", "映射里没有这个 id。", "gone.md", "消失的小节", 0.7, "rerank")
        hits = [orphan, Hit("k.md#0000", "已入库的小节正文。", "k.md", "小节甲", 0.1, "fused")]

        out = expand_to_sections(hits, chunk_map)

        self.assertEqual(len(out), 2)
        self.assertEqual(out[0], orphan)

    def test_keeps_first_occurrence_order(self) -> None:
        """去重后保留首次出现顺序：`b` 小节虽然首块排在后面，但它的位置由首次命中决定。"""
        chunk_map = {
            "m.md#0000": _make_chunk("m.md#0000", "A 节正文。", "m.md", "A", 0),
            "m.md#0001": _make_chunk("m.md#0001", "B 节正文一。", "m.md", "B", 1),
            "m.md#0002": _make_chunk("m.md#0002", "B 节正文二。", "m.md", "B", 2),
            "m.md#0003": _make_chunk("m.md#0003", "C 节正文。", "m.md", "C", 3),
        }
        hits = [
            Hit("m.md#0001", "B 节正文一。", "m.md", "B", 0.9, "fused"),
            Hit("m.md#0000", "A 节正文。", "m.md", "A", 0.8, "fused"),
            Hit("m.md#0002", "B 节正文二。", "m.md", "B", 0.7, "fused"),
            Hit("m.md#0003", "C 节正文。", "m.md", "C", 0.6, "fused"),
        ]
        out = expand_to_sections(hits, chunk_map)

        self.assertEqual([hit.heading for hit in out], ["B", "A", "C"])
        self.assertEqual([hit.chunk_id for hit in out], ["m.md#0001", "m.md#0000", "m.md#0003"])
        # B 节用的是**首次命中**（m.md#0001）的分值，不是后面那块 0.7
        self.assertEqual([hit.score for hit in out], [0.9, 0.8, 0.6])
        self.assertEqual(out[0].text, "B 节正文一。\n\nB 节正文二。")

    def test_empty_input_returns_empty_list(self) -> None:
        self.assertEqual(expand_to_sections([], {}), [])
        self.assertEqual(expand_to_sections([], {"x.md#0000": _make_chunk("x.md#0000", "t", "x.md", "h", 0)}), [])

    def test_result_is_deterministic_and_does_not_mutate_inputs(self) -> None:
        """同输入同输出；且不修改传入的 hits / chunk_map（Hit 是 frozen，但仍要验证）。"""
        chunk_map = {
            "d.md#0000": _make_chunk("d.md#0000", "第一块。", "d.md", "节甲", 0),
            "d.md#0001": _make_chunk("d.md#0001", "第二块。", "d.md", "节甲", 1),
        }
        hits = [
            Hit("d.md#0000", "第一块。", "d.md", "节甲", 0.5, "fused"),
            Hit("d.md#0001", "第二块。", "d.md", "节甲", 0.4, "fused"),
        ]
        snapshot_hits = list(hits)
        snapshot_map = dict(chunk_map)

        first = expand_to_sections(hits, chunk_map)
        second = expand_to_sections(list(hits), dict(chunk_map))

        self.assertEqual(first, second)
        self.assertEqual(hits, snapshot_hits)
        self.assertEqual(chunk_map, snapshot_map)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].text, "第一块。\n\n第二块。")


class SectionModeConfigTests(unittest.TestCase):
    """T-020 修订：`SECTION_MODE` 取代布尔开关 `SECTION_EXPAND`，是三值枚举。

    解析口径必须是「去首尾空白 + 转小写」，且**非法值 / 空值回退 `off`** ——
    配置写错（拼错、写中文、留空）只该退化成安全默认，不该让整个服务起不来。
    """

    def _write_env(self, content: str) -> Path:
        tmp_dir = Path(tempfile.mkdtemp(prefix="rag_env_section_"))
        env_file = tmp_dir / "test.env"
        env_file.write_text(content, encoding="utf-8")
        return env_file

    def test_section_mode_defaults_to_off(self) -> None:
        with isolate_settings_env():
            settings = config.load_settings(env_file=Path(tempfile.mkdtemp(prefix="rag_env_none_")) / "nope.env")
            self.assertEqual(settings.section_mode, "off")
            self.assertIsInstance(settings.section_mode, str)
            self.assertEqual(config.DEFAULTS["SECTION_MODE"], "off")

    def test_valid_modes_are_recognized_case_insensitively(self) -> None:
        with isolate_settings_env():
            for raw, expected in [
                ("off", "off"), ("OFF", "off"), (" off ", "off"),
                ("diverse", "diverse"), ("DiVeRsE ", "diverse"), ("\tDIVERSE\n", "diverse"),
                ("expand", "expand"), (" Expand", "expand"),
            ]:
                env_file = self._write_env(f"SECTION_MODE={raw}\n")
                settings = config.load_settings(env_file=env_file)
                self.assertEqual(settings.section_mode, expected, raw)
                # 与解析函数同一口径
                self.assertEqual(settings.section_mode, config._get_section_mode({"SECTION_MODE": raw}, "SECTION_MODE"))

    def test_invalid_or_empty_value_falls_back_to_off_without_raising(self) -> None:
        with isolate_settings_env():
            for raw in ["乱写", "true", "1", "yes", "0", "expandd", "off off", "中文模式"]:
                env_file = self._write_env(f"SECTION_MODE={raw}\n")
                settings = config.load_settings(env_file=env_file)
                self.assertEqual(settings.section_mode, "off", raw)

            # 空值 / 全空白 → 同样回退 off（空串不是合法值，也不是"未设置"）
            for raw in ["", "   ", "\t"]:
                env_file = self._write_env(f"SECTION_MODE={raw}\n")
                self.assertEqual(config.load_settings(env_file=env_file).section_mode, "off", repr(raw))

    def test_missing_key_and_malformed_env_do_not_raise(self) -> None:
        """缺 key（.env 里根本没写）→ 默认 off；解析失败的行被跳过 → 仍是默认 off。"""
        with isolate_settings_env():
            no_key = self._write_env("MOCK=1\n")
            self.assertEqual(config.load_settings(env_file=no_key).section_mode, "off")
            broken = self._write_env("SECTION_MODE\n# 注释\n")
            self.assertEqual(config.load_settings(env_file=broken).section_mode, "off")

    def test_section_mode_is_independent_from_mock_and_rerank(self) -> None:
        with isolate_settings_env():
            env_file = self._write_env("MOCK=1\nRERANK_ENABLED=1\nSECTION_MODE=expand\n")
            settings = config.load_settings(env_file=env_file)
            self.assertIs(settings.mock, True)
            self.assertIs(settings.rerank_enabled, True)
            self.assertEqual(settings.section_mode, "expand")
            # 没有 SECTION_MODE 时不受其它布尔字段影响
            only_mock = self._write_env("MOCK=1\nRERANK_ENABLED=0\n")
            self.assertEqual(config.load_settings(env_file=only_mock).section_mode, "off")


class DedupeBySectionTests(unittest.TestCase):
    """T-020 修订 / `SECTION_MODE=diverse`：让 top-k 覆盖**更多 `(文档, 小节)`**。

    实测（`expand` 的教训）：把小节撑长会撞 prompt 的 `max_chars` 硬截断（当时默认 3000，
    **T-028 Step 4 已改为 6000**）；而把每个
    缺失要点定位到它真正所在的小节后，主导失分模式是「需要的内容在同一文档的**另一个**
    小节」（`q03` / `q13` 的缺失要点全在另一节）。所以 `diverse` 只去重、**不动 `text`**：
    `text` / `chunk_id` / `score` / `retriever` / `heading` 全部原样保留。
    """

    def test_same_section_hits_dedupe_to_first_without_touching_text(self) -> None:
        hits = [
            Hit("04.md#0001", "方法调用总会重新执行函数。", "04.md", "计算属性缓存 vs 方法", 0.5, "fused"),
            Hit("04.md#0002", "计算属性基于依赖缓存。", "04.md", "计算属性缓存 vs 方法", 0.4, "fused"),
        ]
        out = dedupe_by_section(hits)

        self.assertEqual(len(out), 1)
        # 关键：text 是**首次命中那块的原样文本**，不是小节全文（这正是与 expand 的区别）
        self.assertEqual(out[0].text, "方法调用总会重新执行函数。")
        self.assertEqual(out[0].chunk_id, "04.md#0001")
        self.assertEqual(out[0].score, 0.5)
        self.assertEqual(out[0].retriever, "fused")
        self.assertEqual(out[0].source, "04.md")
        self.assertEqual(out[0].heading, "计算属性缓存 vs 方法")
        self.assertEqual(out[0], hits[0])

    def test_different_sections_are_kept_separately(self) -> None:
        hits = [
            Hit("02.md#0000", "reactive 的局限性一。", "02.md", "reactive() 的局限性", 0.3, "fused"),
            Hit("02.md#0001", "数组注意事项。", "02.md", "数组和集合的注意事项", 0.2, "fused"),
            Hit("02.md#0002", "reactive 的局限性二。", "02.md", "reactive() 的局限性", 0.1, "fused"),
        ]
        out = dedupe_by_section(hits)

        self.assertEqual([hit.chunk_id for hit in out], ["02.md#0000", "02.md#0001"])
        self.assertEqual([hit.heading for hit in out], ["reactive() 的局限性", "数组和集合的注意事项"])
        self.assertEqual([hit.text for hit in out], ["reactive 的局限性一。", "数组注意事项。"])
        self.assertEqual([hit.score for hit in out], [0.3, 0.2])

    def test_same_heading_in_different_sources_are_not_deduped(self) -> None:
        """去重键是 `(source, heading)`：不同文件的同名小节互不影响。"""
        hits = [
            Hit("a.md#0000", "甲的安装说明。", "a.md", "安装", 0.9, "fused"),
            Hit("b.md#0000", "乙的安装说明。", "b.md", "安装", 0.8, "fused"),
        ]
        out = dedupe_by_section(hits)

        self.assertEqual([hit.chunk_id for hit in out], ["a.md#0000", "b.md#0000"])
        self.assertEqual([hit.text for hit in out], ["甲的安装说明。", "乙的安装说明。"])

    def test_empty_input_returns_empty_list(self) -> None:
        self.assertEqual(dedupe_by_section([]), [])

    def test_keeps_first_occurrence_order(self) -> None:
        """保持首次出现顺序，且每个小节取的是**首次出现**那条的分值与文本。"""
        hits = [
            Hit("m.md#0001", "B 节正文一。", "m.md", "B", 0.9, "fused"),
            Hit("m.md#0000", "A 节正文。", "m.md", "A", 0.8, "fused"),
            Hit("m.md#0002", "B 节正文二。", "m.md", "B", 0.7, "rerank"),
            Hit("m.md#0003", "C 节正文。", "m.md", "C", 0.6, "fused"),
            Hit("m.md#0004", "A 节正文二。", "m.md", "A", 0.5, "fused"),
        ]
        out = dedupe_by_section(hits)

        self.assertEqual([hit.heading for hit in out], ["B", "A", "C"])
        self.assertEqual([hit.chunk_id for hit in out], ["m.md#0001", "m.md#0000", "m.md#0003"])
        self.assertEqual([hit.score for hit in out], [0.9, 0.8, 0.6])
        self.assertEqual([hit.retriever for hit in out], ["fused", "fused", "fused"])
        self.assertEqual([hit.text for hit in out], ["B 节正文一。", "A 节正文。", "C 节正文。"])

    def test_result_is_deterministic_and_does_not_mutate_inputs(self) -> None:
        """同输入同输出；且不修改传入的 hits（Hit 是 frozen，但仍要验证列表本身与元素）。"""
        hits = [
            Hit("d.md#0000", "第一块。", "d.md", "节甲", 0.5, "fused"),
            Hit("d.md#0001", "第二块。", "d.md", "节甲", 0.4, "fused"),
            Hit("d.md#0002", "节乙正文。", "d.md", "节乙", 0.3, "fused"),
        ]
        snapshot = list(hits)

        first = dedupe_by_section(hits)
        second = dedupe_by_section(list(hits))

        self.assertEqual(first, second)
        self.assertEqual(hits, snapshot)
        self.assertEqual(len(first), 2)
        self.assertEqual([hit.text for hit in first], ["第一块。", "节乙正文。"])
        # 返回的是原始 Hit 对象（不是副本），所以"原样保留"是可断言的同一性
        self.assertIs(first[0], hits[0])
        self.assertIs(first[1], hits[2])


# ==================== 10. rerank 守卫 / 降级 / 接线（T-021） ====================


def _hit(chunk_id: str) -> Hit:
    """本节夹具：只要一个可辨识的 chunk_id，其余字段固定，避免在断言里混进无关变量。"""
    return Hit(chunk_id, f"{chunk_id} 的正文", "d.md", "节甲", 0.5, "fused")


class RerankGuardTests(unittest.TestCase):
    """T-021：`Retriever.search` 里 rerank 分支的三条契约，全离线锁定。

    动机：rerank 是**真实网络调用**（`src/retrieve.py` 的 `_rerank` 内 `requests.post`），
    而"rerank 到底有没有效果"的结论只有在「三件事同时被证明」时才算数：
    ① `MOCK=1` 时一次都不调用（否则 mock 跑批会偷偷产生真实费用与网络依赖）；
    ② 远端失败时静默降级成融合结果，而不是把异常抛给上层、更不是返回空；
    ③ 远端成功时输出**真的被采用**（顺序生效 + 受 `top_k_final` 截断）——
    否则「rerank 无效」可能只是接线接错了（把返回值丢掉、退回融合结果）。

    成本：`Retriever.__init__` 会 `get_embedder` + `VectorStore`（即 chromadb），所以这里一律
    `object.__new__(Retriever)` 绕开构造，只注入 `search()` 真正用到的属性与可调用对象；
    被替换的方法作为**实例属性**存的是普通函数，不再走描述符绑定，因此签名里没有 `self`。
    """

    def _build_retriever(
        self,
        settings: config.Settings,
        hits: list[Hit],
        rerank,
    ) -> object:
        """造一个只够 `search()` 跑通的最小 Retriever 桩（完全不碰 chromadb / 网络）。"""
        from src.retrieve import Retriever  # 延迟导入，保持与文件既有风格一致

        retriever = object.__new__(Retriever)
        retriever.settings = settings
        # 两路召回排名：只给定 vector 一路，`_rankings` 的返回值形状与真实实现一致
        retriever._rankings = lambda question: {
            "vector": [hit.chunk_id for hit in hits],
            "bm25": [],
        }
        # 融合结果直接用给定 hits：本节的关注点是 rerank 分支，不是 RRF 计分（已由 FusionTests 覆盖）
        retriever._chunk_map = lambda: {}
        retriever._fused_hits = lambda rankings, chunk_map: ([hit.chunk_id for hit in hits], list(hits))
        retriever._rerank = rerank
        return retriever

    def test_mock_mode_never_calls_rerank(self) -> None:
        """`MOCK=1` 即使 `RERANK_ENABLED=1` 也必须零 rerank 调用 —— 这是 mock 模式的全部价值。

        本用例删掉守卫（改成只看 `rerank_enabled`）后会立刻失败：mock 跑批会开始访问真实
        rerank 端点，既产生费用，也让"离线可重复"不复存在。
        """
        with isolate_settings_env():
            base = config.load_settings()
        settings = dataclasses.replace(base, mock=True, rerank_enabled=True)

        calls: list[str] = []

        def _forbidden_rerank(question: str, hits: list[Hit], top_n: int) -> list[Hit]:
            calls.append(question)
            raise AssertionError("MOCK=1 时不应触发 rerank（真实网络调用）")

        retriever = self._build_retriever(settings, [_hit("f1"), _hit("f2"), _hit("f3")], _forbidden_rerank)
        out = retriever.search("x")

        self.assertEqual(calls, [], "rerank 被调用了，mock 模式不再零网络零费用")
        self.assertEqual([hit.chunk_id for hit in out], ["f1", "f2", "f3"])

    def test_rerank_failure_degrades_to_fused_result(self) -> None:
        """远端 rerank 抛错时必须静默降级成**融合结果**，既不抛给上层，也不退化成空列表。

        只打印告警、不改变返回值，是"检索质量可以降级，服务不能挂"的边界；
        返回空列表同样是失败：生成阶段会拿不到任何证据，问答直接变成拒答。
        """
        with isolate_settings_env():
            base = config.load_settings()
        settings = dataclasses.replace(base, mock=False, rerank_enabled=True)
        hits = [_hit("f1"), _hit("f2"), _hit("f3")]

        def _boom(question: str, hits_: list[Hit], top_n: int) -> list[Hit]:
            raise RuntimeError("boom")

        retriever = self._build_retriever(settings, hits, _boom)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            out = retriever.search("x")  # 这里抛异常即用例失败，不需要额外断言

        # 对照：显式关掉 rerank 的同一份融合池
        retriever_off = self._build_retriever(settings, hits, _boom)
        expected = retriever_off.search("x", use_rerank=False)
        self.assertEqual([hit.chunk_id for hit in out], [hit.chunk_id for hit in expected])
        self.assertEqual([hit.chunk_id for hit in out], ["f1", "f2", "f3"])
        self.assertNotEqual(out, [])
        # 降级必须是"可见"的：否则线上会静默丢掉 rerank 而不被察觉
        self.assertIn("[warn] rerank", stdout.getvalue())

    def test_rerank_order_is_actually_used(self) -> None:
        """rerank 的输出必须真的生效：返回顺序 = rerank 给的顺序，且条数受 `top_k_final` 截断。

        这条锁的是"接线"而不是"效果"：若 `search()` 忽略 rerank 返回值直接返回融合结果，
        「rerank 无效」的结论可能纯属接线接错；也不能让 rerank 返回多少就给模型多少
        （`top_n` 只是请求参数，远端不一定守约，切分仍必须由本地 `top_k_final` 把住）。
        """
        with isolate_settings_env():
            base = config.load_settings()
        # 融合池 4 条、top_k_final=4，而 rerank 故意返回 6 条（模拟远端不守 top_n）
        settings = dataclasses.replace(base, mock=False, rerank_enabled=True, top_k_final=4)
        hits = [_hit(f"f{i}") for i in range(4)]
        extra = [_hit("x5"), _hit("x6")]

        def _reverse(question: str, hits_: list[Hit], top_n: int) -> list[Hit]:
            self.assertEqual([hit.chunk_id for hit in hits_], ["f0", "f1", "f2", "f3"])
            return list(reversed(hits_)) + extra

        retriever = self._build_retriever(settings, hits, _reverse)
        out = retriever.search("x")

        self.assertEqual([hit.chunk_id for hit in out], ["f3", "f2", "f1", "f0"])
        self.assertEqual(len(out), settings.top_k_final)


if __name__ == "__main__":
    unittest.main(verbosity=2)
