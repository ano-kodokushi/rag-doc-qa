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

## 安全约定

- 任何真实 key 只允许存在于 `.env`（已 gitignore）或环境变量中。
- `.env.example` 只放占位与默认端点，key 字段一律留空。
- `data/raw/` 下的第三方文档请勿提交（见 `data/raw/README.md`）。

## 相关文档

- 需求契约：`SPEC.md`
- 出题与判分：`eval/README.md`
- 语料准备：`data/raw/README.md`
- 文档来源：`docs/DOC_SOURCES.md`
