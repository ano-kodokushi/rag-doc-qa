# RAG 文档问答（rag-doc-qa）

基于本地文档语料的检索增强问答服务：把 `data/raw/` 里的文档切块、向量化入库，
再用「向量检索 + BM25 关键词检索 + 融合」召回，最后交给大模型生成**带出处**的回答。

- 服务框架：FastAPI
- 生成模型 / Embedding：任意 OpenAI 兼容端点（默认 DeepSeek 生成 + 阿里云百炼 Embedding，见 `.env.example`）
- 向量库：ChromaDB（本地持久化到 `data/chroma/`）
- 评测：`eval/` 下 20 题自建评测集，单跳 / 多跳 / 不可答三类

## 目录结构

```
rag-doc-qa/
├─ .env.example              # 配置模板（复制成 .env 后填 key）
├─ .gitignore
├─ requirements.txt
├─ README.md
├─ SPEC.md                   # 需求契约（唯一权威，不要改）
├─ app/
│  ├─ __init__.py            # 空文件
│  └─ main.py                # FastAPI 服务入口
├─ src/
│  ├─ __init__.py            # 空文件
│  ├─ config.py              # 读 .env，集中配置
│  ├─ chunking.py            # 文档切块
│  ├─ fusion.py              # 多路召回融合
│  ├─ embed.py               # Embedding 调用
│  ├─ store.py               # ChromaDB 读写
│  ├─ bm25.py                # BM25 关键词检索
│  ├─ retrieve.py            # 检索主流程
│  ├─ generate.py            # 生成 + 出处
│  └─ ingest.py              # 语料入库
├─ eval/
│  ├─ __init__.py            # 空文件
│  ├─ metrics.py             # 判分口径
│  ├─ run_eval.py            # 评测入口
│  ├─ questions.example.jsonl# 示例题（复制成 questions.jsonl 再改）
│  └─ README.md              # 出题与判分规范
├─ tests/
│  ├─ __init__.py            # 空文件
│  └─ test_offline.py        # 纯标准库离线单测
├─ data/
│  ├─ raw/                   # 原始语料（.md / .txt / .pdf）
│  │  └─ README.md
│  ├─ chunks.jsonl           # 切块结果（生成物，不入库）
│  └─ chroma/                # 向量库（生成物，不入库）
└─ docs/
   └─ DOC_SOURCES.md         # 建议文档来源
```

约定：`__init__.py` 一律为空文件；模块之间用 `from src.xxx import yyy` 绝对导入，
**所有命令都必须在 `PROJECT_ROOT`（即 `rag-doc-qa\`）下运行**。

## 快速开始

### 第 1 步：先跑 mock 模式（不需要任何 API key、不需要联网）

mock 模式下不发起任何真实网络请求，用于确认目录、导入链路、切块与检索逻辑通顺。

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Set-Location $R

# 1.1 安装依赖（首次，需要联网）
& $P -m pip install -r requirements.txt

# 1.2 离线单测（纯标准库，必须全绿）
& $P -m unittest discover -s "$R\tests" -t $R -v

# 1.3 语法检查（可选，快速自检）
& $P -m compileall -q $R

# 1.4 以 mock 模式起服务
$env:MOCK = "1"
& $P -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开一个终端验证：

```powershell
& $P -c "import urllib.request,json; r=urllib.request.urlopen('http://127.0.0.1:8000/health'); print(r.status, r.read().decode('utf-8'))"
```

### 第 2 步：确认 mock 通过后，再配置真实 key

1. 复制模板：

```powershell
Set-Location "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Copy-Item .env.example .env
```

2. 编辑 `.env`，填入你自己的 key（**只写在 `.env` 里，`.env` 已被 `.gitignore` 忽略，绝不提交、绝不写进本 README 或任何源码**）：
   - `LLM_API_KEY`：生成模型 key（默认 DeepSeek）
   - `EMBED_API_KEY`：Embedding key（默认阿里云百炼）
3. 把 `MOCK=0`（真实模式）。

真实模式需要：可用的网络 + 有效的 API key + `EMBED_DIM` 与实际 embedding 模型维度一致。

### 第 3 步：真实模式入库并起服务

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Set-Location $R

# 3.1 把 data/raw/ 下的文档切块并写入向量库（默认重建集合并打印 files/chunks/elapsed_ms/mocked/sources 汇总）
& $P -m src.ingest

# 可选参数：--no-reset 表示不重建集合、直接增量追加；--raw-dir 覆盖语料目录（默认 data/raw）
& $P -m src.ingest --no-reset
& $P -m src.ingest --raw-dir "data\raw"

# 注意：语料为空（data/raw 下没有 .md/.txt/.pdf）时不会写库，会打印 [error] 并以退出码 1 结束

# 3.2 起服务
& $P -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 第 4 步：跑评测

```powershell
Set-Location "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Copy-Item eval\questions.example.jsonl eval\questions.jsonl
# 按 eval/README.md 的规范把 20 题写好，定稿后不要再改
& $P -m eval.run_eval --mode mock --questions eval/questions.jsonl --out eval/report_mock.json
```

评测参数说明：

- `--mode`：三选一 `retrieval` / `full` / `mock`，必填。
- `--questions`：题目 jsonl 路径，必填。
- `--out`：汇总 JSON 输出路径，必填。
- `--limit N`：只跑前 N 题（可选）。
- `--top-k K`：覆盖检索返回条数（可选）。

先跑 `mock`（不消耗额度、不需要 key）确认链路，再跑 `full` 出真实成绩；
`--mode retrieval` / `--mode full` 都需要先在 `.env` 里配好有效的 API key。

## 运行顺序（重要）

**先跑 mock → 确认离线单测全绿 → 再填 key 走真实模式。**
mock 阶段不消耗任何额度，也能定位绝大多数环境/导入/路径问题；
直接上真实模式会把「环境问题」和「模型问题」混在一起，排查成本高得多。

## 实测结果（2026-09-21）

环境：`data/raw/` 共 **12 份**中文语料（Vue 3 × 5 / FastAPI × 5 / MyBatis-Plus × 1 / 自有 × 1，共 106829 字符），
切块 **400** 块；生成用 DeepSeek `deepseek-chat`，向量化用阿里云百炼 `text-embedding-v3`（1024 维）；
评测集为自建 20 题（单跳 12 / 多跳 5 / 不可答 3，含标准答案与判分口径）。
下表为**最近一次真实运行**（T-015 性能优化之后）：

| 指标 | 值 | 多次运行的范围 |
|---|---|---|
| `accuracy`（要点覆盖率 ≥ 0.8 判对） | **0.50** | 0.45–0.50 |
| `partial_rate` | 0.25 | 0.25–0.35 |
| `wrong_rate` | 0.25 | 0.20–0.25 |
| `refusal_accuracy`（不可答题正确拒答） | **1.00** | **1.00（三次全部一致）** |
| `hit_rate`（检索命中正确文档） | **0.80** | **0.80（三次全部一致）** |
| `avg_latency_ms`（单题端到端） | **1316.3** | 优化前 1654.6 |
| `avg_keypoint_coverage`（连续要点覆盖率，非拒答题均值） | **0.5343** | 用来看桶指标看不见的位移 |

**可选 rerank 的实测（T-021，同进程 A/B）**：默认关闭（`RERANK_ENABLED=0`）。打开后**主指标 `avg_keypoint_coverage` 0.5490 → 0.6373（+0.088）**、`wrong_rate` **0.20 → 0.10**、逐题**升 4 / 降 1**；
代价是单题延迟 **1136 → 3188 ms（+2.05 s）**。**因此默认值保持关闭** —— 收益偏质量、成本偏延迟，由使用方按场景取舍（详见 `docs/EXPERIMENTS.md` E-04）。

按题型拆开（最近一次）：

| 题型 | 题数 | 对 / 部分 / 错 | 检索命中 | accuracy |
|---|---|---|---|---|
| `single_hop` | 12 | 6 / 2 / 4 | 11/12 | 0.50 |
| `multi_hop` | 5 | 1 / 3 / 1 | 5/5 | **0.20** |
| `unanswerable` | 3 | 3 / 0 / 0 | — | **1.00** |

**这几句话必须跟上面的数字一起说，否则会误导：**

1. **有运行间波动**：同输入连跑三次，`accuracy` 实测落在 **0.45–0.50**。`correct` 与 `partial` 的边界取决于模型输出的措辞（要点覆盖率是否过 0.8），模型即使 `temperature=0` 也非逐字确定。请写成「单次运行」或区间，**不要当成固定常数**。
2. **`multi_hop` 是短板，瓶颈在「检索到同一文件的错误小节」，不在生成侧**：多跳题**文件级**检索命中 **5/5**（依据的两篇至少召回到一篇），但实际给模型的常是**错的节**，所以只有 1/5 完全答对。
   这一点我**推翻过自己的第一版结论**：最初据桶指标判定「检索侧无效、瓶颈在生成侧」，改用**连续要点覆盖率**重读同一批数据后发现，候选 4→8 时覆盖率**逐题 5 升 0 降**（多跳均值 0.450 → 0.550）——**检索侧有效，只是被 0.8 的桶阈值挡住了**。复盘见 `docs/EXPERIMENTS.md` 的 E-01 → E-02。
3. **试过「按小节整理上下文」，实测没有净收益，因此默认关闭**：`SECTION_MODE=diverse`（同小节只留最高分块）覆盖率 **0.5343 → 0.5147（更差）**；`SECTION_MODE=expand`（整节进 prompt）**0.5441**，仅在噪声内，却让 **14/20 题**有资料被 3000 字符预算丢掉（`q04` 覆盖率 1.00 → 0.00）。
   三次实验合起来是一句话：**决定成败的是「上下文里有没有那段内容」，而不是怎么排列它**。详见 `docs/EXPERIMENTS.md` E-03。
4. **拒答准确率 100%**：3 道语料里根本没有答案的题全部正确拒答，**一次都没有编造**。
5. **延迟的下降来自一次已量化的性能优化，而不是模型变快**：原先每次检索都会**重新构建一遍 BM25 索引**（占单次检索耗时 **99%**，432.9 ms）。把索引缓存在检索器实例上之后，单次检索 **401.6 → 10.7 ms（-97.3%）**、单题端到端 **1654.6 → 1316.3 ms（-20.4%）**；同进程 A/B 证明**检索结果逐字不变**（差异 0 处），所以延迟下降是白赚的，**准确率的变化与之无关**。

> 逐题明细见 `eval/report_detail.json`（本地产物，被 `.gitignore` 挡住，不入公开仓库）。
> 本 README 里的每条 `$P -m ...` 命令，都已在 2026-09-18 的交接收口轮中**实际执行过**。
> `SECTION_MODE` 的对照实验报告同理（`eval/report_t020_*.json`，本地）。

### 已知限制

- ⚠️ **向量检索层的结果不可跨进程复现**：同一份代码、同一份索引，在不同进程里对同一 query 返回的候选集与排序**会漂移**（chroma 的 HNSW 近似检索所致）；`bm25` 层则始终稳定。
  实测 `hit_rate` 三次真实评测都稳定在 **0.80**，但那是「**指标层稳定**」，**不等于**「每次召回的 chunk 排名一致」。若被追问，如实答即可（详见 `docs/PLAN.md §5.12`）。
- ✅ **`/chat` 的 `latency_ms` 口径已修正（T-014，2026-09-18）**：原实现只统计生成段 —— mock 模式报 **0 ms**、真实模式报 **1251 ms**，而客户端实测分别是约 460 ms 与 **8217 ms**。现改为**请求作用域计时**（lazy 构建 + 检索 + 生成）。
  复测「接口 / 客户端」比值：mock **0.97**（452 / 466.8 ms）、真实 **1.00**（1700 / 1705.4 ms）。
  注意**首次请求会偏大**（含冷启动：mock ≈3.9 s、真实 ≈10.5 s），第 2 次起为稳态 —— 这是刻意保留的口径（见 `docs/BOARD.md` 决策日志）。
  评测报告里的 `avg_latency_ms` 由 `eval/run_eval.py` 独立计时，自始不受此缺陷影响。
- FastAPI 四份语料缺少代码示例（官方源码用构建期宏引用，共 29 处未展开），涉及代码细节的问题在语料里没有依据（见 `docs/DOC_SOURCES.md §5.1`）。
- 自有项目文档（需求 / 库表 / 接口 / 部署 / 状态机）尚未补入，当前语料全是框架官方文档（见 `docs/DOC_SOURCES.md §二`）。
- ⚠️ **rerank 的失败是「静默降级」**：`_rerank` 的任何异常都被吞掉、只打印一行 `[warn] rerank 降级: ...`，随后返回融合结果。
  好处是服务不会挂（已用错误 key 实测：401 → 降级 → 结果与融合结果逐字一致）；代价是**「rerank 没效果」这种结论可能只是降级了** —— 排障时先看有没有这行日志。
- ⚠️ **rerank 模型有生命周期风险**：官方已公告 `gte-rerank` 下线、推荐 `qwen3-rerank`。实测当前端点接受两者（可纯靠 `RERANK_MODEL` 切换），但那是**实测行为、非文档承诺**（见 `docs/PLAN.md §5.15`）。
- ⚠️ **rerank 的 `q14` 是唯一变差的题**（覆盖率 0.500 → 0.250）：rerank **不是单调改进**，它会为了一些题把另一些题的正确答案排下去。

## 安全约定

- 任何真实 key 只允许存在于 `.env`（已 gitignore）或环境变量中。
- `.env.example` 只放占位与默认端点，key 字段一律留空。
- `data/raw/` 下的第三方文档请勿提交（见 `data/raw/README.md`）。

## 相关文档

- 需求契约：`SPEC.md`
- 出题与判分：`eval/README.md`
- 语料准备：`data/raw/README.md`
- 文档来源：`docs/DOC_SOURCES.md`
