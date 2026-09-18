# 评测说明（eval/）

本目录放评测集与判分脚本。评测集是**自建**的，不来自任何公开榜单。

## 1. 题量与配比（20 题）

| 类型 (`type`) | 题数 | 说明 |
| --- | --- | --- |
| `single_hop` | 12 | 单跳：单篇文档内即可找到答案 |
| `multi_hop` | 5 | 多跳：需要跨 2 篇及以上文档综合 |
| `unanswerable` | 3 | 不可答：语料未覆盖，正确答案是拒答 |

合计 20 题。配比不要随意改动，否则各类型得分不可横向比较。

## 2. 文件格式

一行一题，UTF-8，`ensure_ascii=False`（中文直接写，不要写 `\uXXXX`）。字段：

```json
{"id":"q01","type":"single_hop","question":"问题","gold":"标准答案","keypoints":["要点1","要点2"],"gold_sources":["01_xxx.md"],"must_refuse":false}
```

- `id`：唯一，建议 `q01`…`q20`
- `type` ∈ `single_hop` | `multi_hop` | `unanswerable`
- `question`：用户会真实提问的说法，不要写「请问第 3 节讲了什么」这类只有你知道的结构化问法
- `gold`：标准答案
- `keypoints`：判分用的要点列表（`unanswerable` 可为 `[]`）
- `gold_sources`：命中答案所依据的文档文件名（`unanswerable` 为 `[]`）
- `must_refuse`：`unanswerable` 题必须为 `true`，其余为 `false`

## 3. 出题规范

1. 题目必须能由 `data/raw/` 现有语料回答（`unanswerable` 除外），出题前先确认语料里有依据。
2. `gold_sources` 必须是 `data/raw/` 下真实存在的文件名，写错等于自动判错。
3. `multi_hop` 题的 `gold_sources` 至少 2 个不同文档。
4. `unanswerable` 题要问得像真的、但语料确实没有——不要用「语料里有没有写 X」这种送分问法。
5. **题目定稿后不得再修改。** 改题等于换评测集，历史得分不可比；要加题就新增 `id`。
6. 严禁把答案/关键词反向写进 `src/` 或 `app/` 的提示词里去「刷分」。

## 4. 判分口径

- `single_hop` / `multi_hop`：
  - 命中 `keypoints` 的比例 —— 要点覆盖率
  - 是否引用了 `gold_sources` 中的文档 —— 出处正确性
  - 两者都达标记为该题通过
- `unanswerable`（`must_refuse=true`）：模型明确表示语料中没有依据 / 无法回答 记为通过；
  编造答案一律判错（幻觉）。
- 汇总指标：按类型分别给出通过率，并给出总体通过率与平均延迟。
- 具体阈值与实现以 `eval/metrics.py` 为准。

## 5. 怎么用

### 5.1 从示例复制成正式题目

```powershell
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Set-Location $R
Copy-Item eval\questions.example.jsonl eval\questions.jsonl
```

`questions.example.jsonl` 里是 2 条**纯占位示例**（内容不指向真实语料），只用于说明字段格式；
复制成 `eval/questions.jsonl` 后按上面规范改成你的 20 题。

### 5.2 跑评测

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Set-Location $R
& $P -m eval.run_eval
```

必须**在 `PROJECT_ROOT` 下、用 `-m eval.run_eval` 模块方式**运行，
不要用 `python eval/run_eval.py`（相对导入会失败）。

运行前请确认：

1. `data/raw/` 已有语料，且已执行过入库（`& $P -m src.ingest`）
2. `.env` 已配好 key 且 `MOCK=0`（mock 模式下跑评测只验证链路，不代表真实效果）

报告输出为 `eval/report*.json`（已被 `.gitignore` 忽略）。
