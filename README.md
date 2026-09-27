# rag-doc-qa

一个可评测的中文文档 RAG 问答服务：文档入库 → 向量 + BM25 双路召回 → RRF 融合 →（可选）Rerank → 大模型生成带出处的回答。
自带 20 题评测集与判分口径，实测数字与已知限制都写在本文档里。

## 它能做什么

- 把 `data/raw/` 下的 `.md` / `.txt` / `.pdf` 切块、向量化并持久化到本地 ChromaDB；
- 向量检索与 BM25 关键词检索并行，按 RRF 融合后取前若干条交给大模型；
- 回答末尾附 `[编号]` 出处；资料里没有答案时按契约拒答，不编造；
- 用 `eval/` 下的 20 题评测集跑出指标（准确率 / 要点覆盖率 / 命中率 / 拒答准确率 / 延迟）；
- 提供 FastAPI 服务：`POST /chat` 问答、`POST /ingest` 入库、`GET /health` 健康检查。
## 快速开始

mock 模式不发起任何真实网络请求，用来确认目录、导入链路、切块与检索逻辑通顺。

```powershell
python -m pip install -r requirements.txt      # 安装依赖（首次需联网）
python -m unittest discover -s tests -t .       # 离线单测（纯标准库，不需要 key）
python -m compileall -q .                       # 语法检查

$env:MOCK = "1"                                 # 以 mock 模式起服务
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 另开终端验证
python -c "import urllib.request,json; r=urllib.request.urlopen('http://127.0.0.1:8000/health'); print(r.status, r.read().decode('utf-8'))"
```

### 接真实模型

```powershell
Copy-Item .env.example .env
# 编辑 .env：填 LLM_API_KEY（默认 DeepSeek）与 EMBED_API_KEY（默认阿里云百炼），并把 MOCK 改为 0
```

`.env` 已被 `.gitignore` 忽略，不要提交，也不要把 key 写进任何源码或文档。
`data/raw/` 下没有 `.md` / `.txt` / `.pdf` 时不会写库，会打印 `[error]` 并以退出码 1 结束。

```powershell
python -m src.ingest                        # 入库，打印 files / chunks / elapsed_ms / mocked / sources
python -m src.ingest --no-reset             # 可选：增量追加而不重建集合
python -m src.ingest --raw-dir data\raw     # 可选：覆盖语料目录
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 跑评测

```powershell
Copy-Item eval\questions.example.jsonl eval\questions.jsonl
# 按 eval/README.md 的规范把 20 题写好；题库定稿后不要再改，否则历史分数不可比
python -m eval.run_eval --mode mock --questions eval/questions.jsonl --out eval/report_mock.json
```

参数：`--mode`（必填，`retrieval` / `full` / `mock`）、`--questions`（必填）、`--out`（必填）、
`--limit N`（只跑前 N 题）、`--top-k K`（覆盖检索返回条数）。先跑 `mock` 确认链路，再跑 `full` 出真实成绩；
两者都需要先在 `.env` 里配好有效的 API key。

## 它是怎么做的

```
data/raw/*.md|txt|pdf
  → chunking（400 字 / 50 重叠，Markdown 标题作硬边界）
  → embed（text-embedding-v3，1024 维）→ ChromaDB
  → 检索：向量 top-10 + BM25 top-10 → RRF(k=60) → top-15
  → build_prompt（字符预算 6000）→ deepseek-chat → 回答 + [编号] 出处
```

| 关键默认值 | 值 |
|---|---|
| `TOP_K_VEC` / `TOP_K_BM25` / `TOP_K_FINAL` | 10 / 10 / 15 |
| RRF `k` / `CHUNK_SIZE` / `CHUNK_OVERLAP` | 60 / 400 / 50 |
| prompt 字符预算 `max_chars` | 6000 |
| `RERANK_ENABLED` / `SECTION_MODE` | 0 / off（都默认关闭） |

## 实测结果

第一域语料 12 份中文技术文档，106,829 字符（约 10.7 万字），切块 400 块。下表为最近一次真实运行
（各指标定义见 `eval/README.md`）：

| 指标 | 值 |
|---|---|
| `accuracy`（要点覆盖 ≥ 0.8 判对） | 0.75 |
| `partial_rate` / `wrong_rate` | 0.20 / 0.05 |
| `refusal_accuracy`（无答案题正确拒答） | 1.00 |
| `hit_rate`（检索命中正确文档） | 0.85 |
| `avg_latency_ms`（单题端到端） | 1593.95 |
| `avg_keypoint_coverage`（连续要点覆盖率） | 0.8480 |

分题型：`single_hop` 10 / 1 / 1（覆盖率 0.8889）、`multi_hop` 2 / 3 / 0（覆盖率 0.7500）、`unanswerable` 3 / 0 / 0。
这是单次运行：同一配置另一次同进程 A/B 得到 `accuracy` 0.80、覆盖率 0.8676，差异来自大模型输出的措辞
（`temperature=0` 也不保证逐字一致），请按区间理解。自动判分本身偏高：逐题人工复核 9 道有变化的题，
发现 2 道被高估——纯字面匹配分不清"答出要点"与"提到该词，哪怕是在否定它"。把这两题按零改善计，
保守口径是 `accuracy` 0.50 → 0.70、覆盖率 0.5343 → 0.7794，对外只用这个下界，即 +0.20。

一次有效的调参：项目早期主指标是 `accuracy` 0.45~0.50。逐层排查后定位到：检索窗口里的候选被 prompt 的字符预算整条丢掉——
`TOP_K_FINAL` 从 4 加到 8 / 12 / 15，送进模型的 prompt 逐字相同（都被当时的 3000 字符预算截在 7 条资料）。
把两者成对放大（4 → 15、3000 → 6000）后，覆盖率 0.5343 → 0.8676，错误率 0.25 → 0.05；代价是单题 prompt token 约 3.2 倍。
两个参数缺一不可：`TOP_K_FINAL` 只负责把候选取回来，`max_chars` 才让它真的送到模型面前。
另有一次已量化的性能优化：原先每次检索都会重建 BM25 索引（占单次检索耗时 99%），把索引缓存在检索器实例上之后，
单次检索 401.6 → 10.7 ms（-97.3%），同进程 A/B 证明结果逐字不变。

## 已知限制

1. 多跳题是最弱的一类：2 / 5 对，覆盖率 0.7500，低于单跳的 0.8889。它在另一套完全不同的语料域上同样最弱，
   所以更像题型固有的难度，而不是这套语料的问题。窗口与预算放大后它明显改善（0.4500 → 0.7500），但仍未解决。
2. 混合召回不优于仅向量。同进程三路对照（唯一自变量是用哪几路做 RRF）：`avg_keypoint_coverage`
   仅向量 0.6275、仅 BM25 0.5294、混合 0.5343（`accuracy` 0.60 / 0.45 / 0.50）。两路各有所长
   （单跳向量 0.7222 最强、多跳 BM25 0.5000 最强），问题出在等权融合方式。数字取自 `TOP_K_FINAL=4` 时代的旧默认值；
   结论是"等权 RRF 不是好的组合方式"，因此本仓库不宣称混合检索提升了准确率。
3. 可选 Rerank 对多跳题零效果。打开后覆盖率 0.5490 → 0.6373、错误率 0.20 → 0.10，但收益全部来自单跳题
   （单跳 0.5694 → 0.6944，多跳 0.5000 → 0.5000）；代价是单题延迟 1136 → 3188 ms，所以默认仍关闭。
4. 向量层检索不可跨进程复现：ChromaDB 的 HNSW 是近似检索，指标层稳定但逐次召回排序会漂移；BM25 那一路稳定。
5. 第二语料域的语料不入公开仓库（本人课程作业，含学号与同学、导师姓名），所以 clone 之后只能复现第一域的数字。

## 第二语料域

同一套代码另接了一套语料，验证架构可迁移性；只换 4 个环境变量，代码与契约零改动：

```powershell
$env:CHROMA_DIR = "data/chroma_se"; $env:RAW_DIR = "data/raw_se"
$env:CHUNKS_FILE = "data/chunks_se.jsonl"; $env:COLLECTION = "doc_qa_se"
```

该域 19 份 / 169,083 字 / 830 块，20 题基线 `accuracy` 0.95。上面那组参数放大的改动在它上面没有造成退化
（覆盖率 0.9345 → 0.9748，`accuracy` 与分题型桶分布完全不变）——已经答对的题，给再多上下文也不会更对。
两个域的数字不可直接比较：语料风格与题库可答性都不同。

## 目录与文档

`app/main.py` 是服务入口；`src/` 放核心实现（config / chunking / embed / store / bm25 / retrieve / fusion / generate / ingest）；
`eval/` 放判分口径、评测入口与出题规范；`tests/test_offline.py` 是纯标准库离线单测；
`data/raw/` 是语料输入，`data/chunks.jsonl` 与 `data/chroma/` 是生成物（不入库）。
模块之间用 `from src.xxx import yyy` 绝对导入，所有命令都在仓库根目录下运行。
延伸阅读：`SPEC.md`（需求契约，冲突时以它为准）· `eval/README.md`（出题与判分规范）·
`docs/EXPERIMENTS.md`（全部对照实验，含被推翻的结论，原样保留）· `docs/PLAN.md`（任务卡与验收标准）·
`docs/BOARD.md`（进度、决策日志与交接）· `docs/DOC_SOURCES.md`（第一域语料来源）。
所有 key 只从环境变量或 `.env` 读取，仓库内不存在任何真实 key。

MIT，见 `LICENSE`。
