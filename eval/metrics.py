"""离线评测度量（纯标准库实现）。

契约来源：SPEC.md 293-308 行的冻结签名与语义。
本模块只依赖 Python 标准库（``re`` / ``unicodedata``），不导入任何第三方库，
所有函数均为纯函数、无副作用、对同一输入结果完全确定（不依赖随机、时间或字典迭代序）。

函数总览::

    normalize_answer(s) -> str
    exact_match(pred, gold) -> bool
    contains_match(pred, gold) -> bool
    keypoints_match(pred, keypoints) -> float
    score_answer(pred, gold, keypoints, must_refuse) -> str
    hit_at_k(retrieved_ids, gold_sources, k) -> bool
    citation_hit(citations, gold_sources) -> bool
    aggregate(records) -> dict
"""

from __future__ import annotations

import re
import unicodedata

__all__ = [
    "normalize_answer",
    "normalize_answer_keep_dots",
    "exact_match",
    "contains_match",
    "keypoints_match",
    "score_answer",
    "hit_at_k",
    "citation_hit",
    "aggregate",
]

# 需要剔除的标点（中英文括号、方括号、空心方括号、引号、句读号等）。
# NFKC 归一化后，全角逗号/句号/问号/感叹号等会先变成半角形态，故两套都列出。
_PUNCTUATION = "，。、；：？！,.;:?!()（）[]【】\"'"

# 去标点采用白名单方式：只保留「字母 / 数字 / 下划线」。
# `\w` 在 Python 的 `re` 默认（Unicode）语义下包含 CJK 汉字、假名等，
# 因此中文关键点不会被误删；而各类标点（含 NFKC 归一化后的 ASCII 标点、
# 全角标点、方括号、引号等）都会被剔除，不受 `_PUNCTUATION` 枚举是否完备影响。
_PUNCT_RE = re.compile(r"[\W_]+", re.UNICODE)

# 与 `_PUNCT_RE` 同类，但额外保留点号 `.`（用于 chunk_id / 文件名的来源比对，
# 因为扩展名分隔符需要保留）。
_PUNCT_KEEP_DOTS_RE = re.compile(r"[^\w.]+", re.UNICODE)

# 判定「拒答」的关键词，命中任意一个即视为模型明确表示无法回答。
_REFUSAL_MARKERS = ("无法回答", "没有相关", "资料中未", "未提及")

# `score_answer` 的三种取值
CORRECT = "correct"
PARTIAL = "partial"
WRONG = "wrong"


def normalize_answer(s: str) -> str:
    """归一化答案文本，用于宽松比较。

    处理顺序：

    1. ``lower()`` 转小写；
    2. ``unicodedata.normalize("NFKC", ...)`` 做全角 → 半角（并顺带统一
       兼容字符，例如全角字母、全角数字、全角标点）；
    3. 去所有空白（NFKC 已把全角空格 U+3000 变成半角空格，故仅需处理空白类字符）；
    4. 去标点（``，。、；：？！,.;:?!()（）[]【】"'`` 等）。

    非字符串输入按 ``str(s)`` 处理，保证函数不会抛异常。
    """
    text = str(s).lower()
    text = unicodedata.normalize("NFKC", text)
    # 去所有空白（含全角空格、制表符、换行、不间断空格等）
    text = "".join(ch for ch in text if not ch.isspace())
    # 去标点：只保留字母、数字、下划线（含 CJK 汉字，汉字属于字母类）
    return _PUNCT_RE.sub("", text)


def normalize_answer_keep_dots(s: str) -> str:
    """与 ``normalize_answer`` 相同，但**保留**点号 ``.``。

    仅用于 chunk_id / 文件名的来源比对：``"服务说明.md#0001"`` 归一化后为
    ``"服务说明.md0001"``，既去掉了 ``#``，又保留了扩展名分隔符 ``.``，
    从而可以安全地做前缀比较。非字符串输入按 ``str(s)`` 处理。
    """
    text = str(s).lower()
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if not ch.isspace())
    return _PUNCT_KEEP_DOTS_RE.sub("", text)


def exact_match(pred: str, gold: str) -> bool:
    """归一化后完全相等即为 True；``gold`` 归一化后为空则返回 False。"""
    gold_norm = normalize_answer(gold)
    if not gold_norm:
        return False
    return normalize_answer(pred) == gold_norm


def contains_match(pred: str, gold: str) -> bool:
    """归一化后 ``gold`` 是 ``pred`` 的子串即为 True；``gold`` 归一化后为空则返回 False。"""
    gold_norm = normalize_answer(gold)
    if not gold_norm:
        return False
    return gold_norm in normalize_answer(pred)


def keypoints_match(pred: str, keypoints: list[str]) -> float:
    """返回关键点命中比例（0.0..1.0）。

    - 逐个关键点判断其归一化形态是否出现在归一化后的预测文本中；
    - 归一化后为空的关键点（如纯标点）跳过、不计入分母；
    - ``keypoints`` 为空（或全部为空串）时返回 ``0.0``。
    """
    if not keypoints:
        return 0.0

    pred_norm = normalize_answer(pred)
    total = 0
    hit = 0
    for point in keypoints:
        point_norm = normalize_answer(point)
        if not point_norm:
            continue
        total += 1
        if point_norm in pred_norm:
            hit += 1

    if total == 0:
        return 0.0
    return hit / total


def score_answer(pred: str, gold: str, keypoints: list[str], must_refuse: bool) -> str:
    """按 SPEC 293-308 的规则给单条预测打分，返回 ``"correct"`` / ``"partial"`` / ``"wrong"``。

    - ``must_refuse=True``：预测包含 ``无法回答`` / ``没有相关`` / ``资料中未`` / ``未提及``
      任一 → ``"correct"``，否则 ``"wrong"``（不做 partial）；
    - 否则：``keypoints_match >= 0.8`` 或 ``exact_match`` → ``"correct"``；
      ``keypoints_match > 0`` 或 ``contains_match`` → ``"partial"``；其余 → ``"wrong"``。

    拒答判定在预测的**原始文本**上进行（关键词匹配不需要归一化，归一化会去掉标点但保留汉字，
    两种方式对本契约的关键词等价）。
    """
    if must_refuse:
        text = str(pred)
        for marker in _REFUSAL_MARKERS:
            if marker in text:
                return CORRECT
        return WRONG

    ratio = keypoints_match(pred, keypoints)
    if ratio >= 0.8 or exact_match(pred, gold):
        return CORRECT
    if ratio > 0 or contains_match(pred, gold):
        return PARTIAL
    return WRONG


def _strip_ext(name: str) -> str:
    """去掉文件名末尾的扩展名（``a.md`` → ``a``，目录名 ``v1.2`` 也按同样规则处理）。"""
    if "." in name:
        head, _, _tail = name.rpartition(".")
        if head:
            return head
    return name


def _source_matches(chunk_id: str, source: str) -> bool:
    """判断单个 ``chunk_id`` 是否来自 ``source``（文件名）。

    chunk_id 形如 ``"服务说明.md#0000"``，而 ``gold_sources`` 里可能是
    ``"01_订单状态机.md"``（带扩展名）或 ``"01_订单状态机"``（去扩展名）。
    判定语义 = 「文件名位于 chunk_id 的前缀里」，因此：

    1. 对原始字符串做大小写 / 全角半角 / 空白归一化（**保留** ``.``，去掉 ``#`` 等符号）；
    2. 若 ``chunk_id`` 以 ``source`` 开头 → 命中；
    3. 否则去掉 ``source`` 的扩展名再比一次，用于覆盖
       ``"a.md#0000"`` vs ``"a.md"`` 之外的写法差异（例如 ``gold_sources`` 写作 ``"01_订单状态机"``
       而 chunk_id 写作 ``"01_订单状态机.md#0002"``）；这一步不会引入误判，因为第 2 步
       要求 chunk_id 真正以该来源名开头。
    """
    chunk = normalize_answer_keep_dots(chunk_id)
    source_norm = normalize_answer_keep_dots(source)
    if not chunk or not source_norm:
        return False
    if chunk.startswith(source_norm):
        return True
    return chunk.startswith(_strip_ext(source_norm))


def hit_at_k(retrieved_ids: list[str], gold_sources: list[str], k: int) -> bool:
    """检索命中判定：``gold_sources`` 中任一文件名出现在 ``retrieved_ids[:k]`` 里 → True。

    - ``gold_sources`` 为空 → False；
    - ``k <= 0`` → False（取不到任何前缀）；
    - 逐个对比时对 chunk_id / 文件名做与 ``normalize_answer`` 同源的宽松匹配
      （大小写、全角半角、空白差异不影响判定），并允许 ``gold_sources`` 省略扩展名。
    """
    if not gold_sources:
        return False
    if k <= 0:
        return False

    shown = retrieved_ids[:k]
    if not shown:
        return False

    for source in gold_sources:
        for chunk_id in shown:
            if _source_matches(str(chunk_id), str(source)):
                return True
    return False


def citation_hit(citations: list[str], gold_sources: list[str]) -> bool:
    """引用命中判定。

    **语义局限（重要）**：``citations`` 只是从模型回答里抽出的 ``[编号]`` 列表
    （形如 ``["1", "2"]``），自身**不含**来源文件名信息；而命中判定需要知道
    每个编号指向哪篇文档，这依赖回答生成时的检索上下文 / 引用映射，本契约并未提供。
    因此这里无法真正判定「引用编号是否指向 gold_sources」。

    本实现采取契约允许的保守语义：``citations`` 非空且 ``gold_sources`` 非空时返回 True，
    否则 False（即仅判断「存在引用」且「本题确有应引用来源」）。
    若后续评测链路能把编号映射成来源文件名，应改由调用方先把编号解析成来源名，
    再复用 ``hit_at_k`` 的匹配逻辑。
    """
    if not citations:
        return False
    if not gold_sources:
        return False
    # 契约允许的最简语义：至少存在一个非空引用编号，且本题存在应引用来源。
    return any(str(item).strip() for item in citations)


def _is_refusal_record(rec: dict) -> bool:
    """判断一条记录是否属于「拒答题」（用于 ``refusal_accuracy`` 的分母/分子）。

    判定优先级（严格按此顺序，先命中先返回）：

    1. ``rec.get("must_refuse") is True`` → 是（显式值为真，尊重上游标注）；
    2. ``"must_refuse" not in rec`` 且 ``rec.get("type") == "unanswerable"`` → 是
       （**兜底**：字段缺失时用题目类型推断）；
    3. 其余 → 否。

    为什么需要第 2 条兜底：``must_refuse`` 由上游逐题标注（``eval/questions.jsonl``
    的字段），一旦上游漏传该字段，第 1 条永远不会命中，``refusal_accuracy`` 就会
    恒为 ``0.0``，让拒答能力看起来完全失效——这是"缺字段"被误读成"能力为零"的
    静默错误。由于 ``type == "unanswerable"`` 按 SPEC 124-125 行本就是
    应拒答的题型，用它兜底可以从题目类型恢复出拒答题集合。

    注意第 2 条要求字段**完全缺失**（``not in``），因此显式写了
    ``must_refuse=None`` / ``False``（包括 ``unanswerable`` 题）的记录不参与兜底：
    ``None is True`` 为假，且键存在 → 被排除。这样显式标注始终优先于类型推断，
    上游可以用 ``must_refuse=False`` 明确否决一道 ``unanswerable`` 题的拒答预期。
    """
    if rec.get("must_refuse") is True:
        return True
    if "must_refuse" not in rec and rec.get("type") == "unanswerable":
        return True
    return False


def aggregate(records: list[dict]) -> dict:
    """聚合评测记录，返回 6 个指标的字典。

    返回结构::

        {"n": int, "accuracy": float, "partial_rate": float,
         "wrong_rate": float, "refusal_accuracy": float, "hit_rate": float}

    - ``accuracy`` = ``score == "correct"`` 的占比；
    - ``partial_rate`` = ``score == "partial"`` 的占比；
    - ``wrong_rate`` = ``score == "wrong"`` 的占比；
    - ``refusal_accuracy`` = 拒答题集合中 ``score == "correct"`` 的占比
      （集合为空 → 0.0）；
    - ``hit_rate`` = ``hit`` 为真的占比（``hit`` 取记录里的 ``hit`` 字段，
      非 ``True`` 的取值一律按未命中处理）。

    拒答题集合的判定规则（见 ``_is_refusal_record``）：

    - ``rec.get("must_refuse") is True`` → 属于拒答题；
    - **兜底**：记录里**没有** ``must_refuse`` 键、且 ``rec.get("type") == "unanswerable"``
      → 属于拒答题；
    - 其余 → 不属于。

    需要这条兜底的理由：``must_refuse`` 是上游逐题标注的字段，上游一旦漏传，
    仅看该字段会让拒答题集合恒为空、``refusal_accuracy`` 恒为 ``0.0``，
    把"字段缺失"误报成"拒答能力为零"。按 SPEC 124-125 行，``type == "unanswerable"``
    本身即应拒答，故在字段缺失时可据此恢复拒答题集合（防御性兜底，不改变正常路径）。
    显式给出的 ``must_refuse``（含 ``False`` / ``None``）始终优先：它们不是"缺失"，
    既不会被兜底补进来，也不会被覆盖。

    所有除零情况一律返回 ``0.0``；``records`` 为 ``[]`` → ``n == 0`` 且各比率均为 ``0.0``。
    ``n`` 只统计 ``dict`` 类型的记录，非 dict 元素被忽略。
    """
    rows = [r for r in records if isinstance(r, dict)]
    n = len(rows)
    if n == 0:
        return {
            "n": 0,
            "accuracy": 0.0,
            "partial_rate": 0.0,
            "wrong_rate": 0.0,
            "refusal_accuracy": 0.0,
            "hit_rate": 0.0,
        }

    correct = 0
    partial = 0
    wrong = 0
    hit = 0
    refusal_total = 0
    refusal_correct = 0

    for row in rows:
        score = row.get("score")
        if score == CORRECT:
            correct += 1
        elif score == PARTIAL:
            partial += 1
        elif score == WRONG:
            wrong += 1

        if row.get("hit") is True:
            hit += 1

        if _is_refusal_record(row):
            refusal_total += 1
            if score == CORRECT:
                refusal_correct += 1

    return {
        "n": n,
        "accuracy": correct / n,
        "partial_rate": partial / n,
        "wrong_rate": wrong / n,
        "refusal_accuracy": (refusal_correct / refusal_total) if refusal_total else 0.0,
        "hit_rate": hit / n,
    }
