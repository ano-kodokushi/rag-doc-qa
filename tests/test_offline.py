"""离线单测：只依赖标准库 + src.config / src.chunking / src.fusion / src.embed / src.ingest / eval.metrics。

覆盖 SPEC.md 332-339 要求的 6 类契约。运行方式见 SPEC.md §6：
    & $P -m unittest discover -s "$R\\tests" -t $R -v
"""

from __future__ import annotations

import contextlib
import dataclasses
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
from src.fusion import dedupe_keep_order, rrf_fuse  # noqa: E402
from src.ingest import read_raw_files  # noqa: E402

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
            self.assertEqual(settings.top_k_final, 4)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
