"""评测 CLI：三种模式跑评测集，产出 report.json 与汇总指标。

用法（在 rag-doc-qa/ 目录下，沙箱内用 python 绝对路径）：
    python -m eval.run_eval --mode retrieval|full|mock \
        --questions eval/questions.jsonl --out eval/report.json [--limit N] [--top-k K]

模式语义（SPEC 冻结）：
- retrieval：只跑检索，不构造 Generator（避免无谓的 API key 校验），pred=""；
- full     ：检索 + 生成（真实 Embedder + Generator，需要 API key / 网络 / chromadb）；
- mock     ：load_settings() 后 dataclasses.replace(..., mock=True)，走 MockEmbedder +
             MockGenerator —— 不需要 API key、不需要网络，但仍需 chromadb。

本文件只用标准库 + 项目内模块；不硬编码任何题目/语料内容。
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

# 允许从任意工作目录直接执行（例如 python eval/run_eval.py）：把项目根加入 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from eval.metrics import aggregate, citation_hit, hit_at_k, keypoints_match, score_answer
from src.config import Settings, load_settings
from src.generate import get_generator
from src.retrieve import Retriever

MODES = ("retrieval", "full", "mock")

# 记录键（SPEC §5 冻结顺序 + 本文件新增的 must_refuse 与 keypoint_coverage，
# 仅用于结构自检，不改变既有键名）。
# must_refuse 放在 gold 之后、keypoint_coverage 放在最后，与 run_once 里的构造顺序保持一致。
RECORD_FIELDS = (
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
    "keypoint_coverage",
)

# 汇总字段顺序（前 7 个来自 aggregate 与 summarize，最后一个是所有记录 latency_ms 的平均）。
# avg_keypoint_coverage 是**向后兼容扩展**：既有 7 个字段的名字、顺序、语义一律不变
# （理由与登记见 docs/PLAN.md §5 已知限制第 13 条）。
SUMMARY_FIELDS = (
    "n",
    "accuracy",
    "partial_rate",
    "wrong_rate",
    "refusal_accuracy",
    "hit_rate",
    "avg_latency_ms",
    "avg_keypoint_coverage",
)


# ─────────────────────────── 数据读写 ───────────────────────────


def load_questions(path: Path) -> tuple[list[dict], int]:
    """读 jsonl 题目；坏行（非 JSON / 非对象 / 缺 question）跳过。

    返回 (题目列表, 被跳过的坏行数)。文件不存在 → ([], 0)。
    """
    if not path.exists():
        return [], 0
    questions: list[dict] = []
    bad = 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if not isinstance(obj, dict) or not str(obj.get("question", "")).strip():
                bad += 1
                continue
            questions.append(obj)
    return questions, bad


def write_json(path: Path, payload: dict) -> None:
    """写 JSON（父目录自动创建，utf-8，ensure_ascii=False）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─────────────────────────── 单题评测 ───────────────────────────


def _must_refuse(question: dict) -> bool:
    """题目是否「必须拒答」。

    取值优先级（SPEC §4 冻结格式：题目可显式带 ``must_refuse``）：

    1. 题目显式带 ``must_refuse`` 键 → 按其真值（``bool(...)``）；
    2. 题目没有该键 → 用 ``type == "unanswerable"`` 推导。

    该函数是唯一取值来源：``run_once`` 既用它打分、也用它写记录，
    保证「打分口径」与「记录里的 must_refuse」严格同源。
    """
    if "must_refuse" in question:
        return bool(question.get("must_refuse"))
    return str(question.get("type", "")) == "unanswerable"


def run_once(
    settings: Settings,
    question: dict,
    mode: str,
    retriever: Retriever,
    generator: object | None,
    top_k: int,
) -> dict:
    """跑一道题，返回冻结格式的记录 dict。"""
    qid = str(question.get("id", ""))
    qtype = str(question.get("type", ""))
    qtext = str(question.get("question", ""))
    gold = str(question.get("gold", ""))
    keypoints = question.get("keypoints") or []
    if not isinstance(keypoints, list):
        keypoints = []
    gold_sources = question.get("gold_sources") or []
    if not isinstance(gold_sources, list):
        gold_sources = []
    must_refuse = _must_refuse(question)

    started = time.perf_counter()
    hits = retriever.search(qtext, top_k=top_k) if qtext else []
    retrieved_ids = [h.chunk_id for h in hits]

    pred = ""
    citations: list[str] = []
    if mode != "retrieval" and generator is not None:
        answer = generator.answer(qtext, hits)
        pred = answer.text
        citations = list(answer.citations or [])

    latency_ms = int(round((time.perf_counter() - started) * 1000))

    return {
        "id": qid,
        "type": qtype,
        "question": qtext,
        "pred": pred,
        # 注意：键名按 SPEC 固定为 gold / retrieved_ids[:k] / hit / citation_hit
        "gold": gold,
        # must_refuse 为新增键（aggregate 的 refusal_accuracy 依据它计算）；
        # 取值与下面 score_answer 的入参同源（同一个 must_refuse 变量），
        # 避免「打分用推导值、记录写原始值」的不一致。
        "must_refuse": must_refuse,
        "score": score_answer(pred, gold, keypoints, must_refuse),
        "retrieved_ids": retrieved_ids[:top_k],
        "hit": hit_at_k(retrieved_ids, gold_sources, top_k),
        "citation_hit": citation_hit(citations, gold_sources),
        "latency_ms": latency_ms,
        # 连续指标（新增键，向后兼容）：本题的关键点覆盖率，0.0..1.0。
        # 取值与 score_answer 的分桶依据同源（同一个 keypoints 列表、同一个
        # keypoints_match），保证「桶」与「连续值」永远出自一把尺子；
        # 拒答题的 keypoints 为空 → 恒为 0.0，aggregate 会把它排除在均值之外。
        # 为什么要有它：桶指标（阈值 0.8）看不见 0.45 → 0.55 这类真实变化，
        # 详见 docs/EXPERIMENTS.md E-02。
        "keypoint_coverage": keypoints_match(pred, keypoints),
    }


def summarize(records: list[dict]) -> dict:
    """aggregate 的 7 个字段 + avg_latency_ms（无记录时 0.0）。"""
    summary = dict(aggregate(records))
    if records:
        avg = sum(float(r.get("latency_ms", 0) or 0) for r in records) / len(records)
    else:
        avg = 0.0
    summary["avg_latency_ms"] = avg
    return {field: summary.get(field, 0.0 if field != "n" else 0) for field in SUMMARY_FIELDS}


def format_summary(summary: dict) -> str:
    """汇总文本（百分比用百分数，便于人读）。"""
    lines = [
        f"题目数        n = {summary['n']}",
        f"准确率        accuracy = {summary['accuracy']:.4f}",
        f"部分正确率    partial_rate = {summary['partial_rate']:.4f}",
        f"错误率        wrong_rate = {summary['wrong_rate']:.4f}",
        f"拒答准确率    refusal_accuracy = {summary['refusal_accuracy']:.4f}",
        f"检索命中率    hit_rate = {summary['hit_rate']:.4f}",
        f"平均延迟      avg_latency_ms = {summary['avg_latency_ms']:.2f}",
        # 连续主指标（E-02 确立）：桶指标看不见的改进靠它才看得见；
        # 分母是**非拒答**记录数，故与 n 不同。
        f"平均覆盖率    avg_keypoint_coverage = {summary['avg_keypoint_coverage']:.4f}",
    ]
    return "\n".join(lines)


# ─────────────────────────── CLI ───────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.run_eval",
        description="RAG 文档问答评测：retrieval / full / mock 三模式",
    )
    parser.add_argument("--mode", required=True, choices=list(MODES))
    parser.add_argument("--questions", required=True, help="题目 jsonl 路径")
    parser.add_argument("--out", required=True, help="汇总 JSON 输出路径")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 题")
    parser.add_argument("--top-k", type=int, default=None, help="覆盖检索返回条数")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    questions_path = Path(args.questions)
    out_path = Path(args.out)

    questions, bad_lines = load_questions(questions_path)
    if bad_lines:
        print(f"[warn] 跳过 {bad_lines} 行坏数据：{questions_path}")
    if not questions:
        print(
            f"[error] 题库为空或文件不存在：{questions_path}（请先准备 jsonl 题目）",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.limit is not None:
        if args.limit <= 0:
            print(f"[error] --limit 必须为正整数，收到 {args.limit}", file=sys.stderr)
            sys.exit(1)
        questions = questions[: args.limit]
    if args.top_k is not None and args.top_k <= 0:
        print(f"[error] --top-k 必须为正整数，收到 {args.top_k}", file=sys.stderr)
        sys.exit(1)

    base_settings = load_settings()
    settings = dataclasses.replace(base_settings, mock=True) if args.mode == "mock" else base_settings
    if args.top_k is not None:
        settings = dataclasses.replace(settings, top_k_final=args.top_k)
    top_k = int(args.top_k if args.top_k is not None else settings.top_k_final)

    # retrieval 模式不构造 Generator（避免无谓的 API key 校验）
    retriever = Retriever(settings)
    generator = None if args.mode == "retrieval" else get_generator(settings)

    print(f"[info] mode={args.mode} mock={settings.mock} top_k={top_k} n={len(questions)}")

    records = [
        run_once(settings, question, args.mode, retriever, generator, top_k)
        for question in questions
    ]

    summary = summarize(records)
    write_json(out_path, summary)

    print(format_summary(summary))
    print(f"[info] 汇总已写入 {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
