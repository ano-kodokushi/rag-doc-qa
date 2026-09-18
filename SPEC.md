# SPEC · rag-doc-qa（冻结接口契约）

> 本文件是**唯一权威契约**。所有 Worker 只按本文件实现，不得自行改名、改签名、改文件路径。
> 项目根：`C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa\`（下称 `PROJECT_ROOT`）

---

## 0. 目标与非目标

**目标**：一个可跑通、可评测的最小 RAG 问答服务——文档入库 → 混合检索（向量 + BM25）→ RRF 融合 →（可选）Rerank → LLM 生成带引用 → 20 题评测出真实数字。

**非目标（禁止实现）**：前端页面、登录鉴权、多用户、Redis 缓存、Docker/K8s、LangChain/LlamaIndex、微调、向量库集群、异步任务队列。

**语料**：`data/raw/` 下的 `.md` / `.txt` / `.pdf`（一期 10 份）。语料由用户提供，代码不得硬编码任何语料内容或题目内容。

---

## 1. 目录结构（必须完全一致）

```
rag-doc-qa/
├─ .env.example
├─ .gitignore
├─ requirements.txt
├─ README.md
├─ SPEC.md                      # 本文件（不要改）
├─ app/__init__.py
├─ app/main.py                  # FastAPI 服务
├─ src/__init__.py
├─ src/config.py
├─ src/chunking.py
├─ src/fusion.py
├─ src/embed.py
├─ src/store.py
├─ src/bm25.py
├─ src/retrieve.py
├─ src/generate.py
├─ src/ingest.py
├─ eval/__init__.py
├─ eval/metrics.py
├─ eval/run_eval.py
├─ eval/questions.example.jsonl
├─ eval/README.md
├─ tests/__init__.py
├─ tests/test_offline.py
├─ data/raw/README.md
└─ docs/DOC_SOURCES.md
```

`__init__.py` 一律为空文件。所有模块用 `from src.xxx import yyy` 绝对导入，**从 PROJECT_ROOT 运行**。

---

## 2. 全局硬约束（违反即 reject）

1. **第三方库一律延迟导入**：`chromadb` / `openai` / `fastapi` / `jieba` / `rank_bm25` / `pypdf` / `requests` **不得出现在模块顶层 import**，只能写在函数或方法体内。
   - 例外：`app/main.py` 可以顶层 `from fastapi import FastAPI`。
   - 原因：离线单测要能 `import src.store` / `import src.embed`，而这些库尚未安装。
2. **标准库可用的不引第三方**：`json` / `pathlib` / `hashlib` / `math` / `re` / `dataclasses` / `typing` / `urllib`。`numpy`、`pandas` 一律**不得**在 `src/` 中使用。
3. **Mock 模式必须离线可跑**：`settings.mock=True` 时 `MockEmbedder` / `MockGenerator` 不得访问网络、不得读 API key。
4. **禁止硬编码期望结果**：不得针对特定输入、特定文件名、特定题目返回固定输出。任何返回都必须由输入推导。
5. **确定性**：同一输入多次调用结果必须完全一致（不得依赖随机、时间、字典迭代序）。
6. **编码**：所有文件写入一律 `encoding="utf-8"`；jsonl 写入用 `ensure_ascii=False`。
7. **运行环境**：本机沙箱内 `PATH` 可能为空串，`python` / `node` / `git` **不能裸调**。Python 一律用绝对路径：
   `C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe`
   ⚠️ 机器上另有一套 Anaconda **Python 3.7**（`C:\Users\a2695\anaconda3\python.exe`），**禁止使用**。
8. **不得改动超出 inScope 的文件**；不得修改 `SPEC.md`。
9. Python 版本按 **3.12** 写，可使用 `X | None` 类型标注。

---

## 3. 环境变量（`.env`）

```ini
# ── 生成模型（OpenAI 兼容端点）──
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=
LLM_MODEL=deepseek-chat

# ── Embedding（默认阿里云百炼 OpenAI 兼容端点）──
EMBED_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBED_API_KEY=
EMBED_MODEL=text-embedding-v3
EMBED_DIM=1024
EMBED_BATCH=10

# ── Rerank（二期可选；关闭时不发任何请求）──
RERANK_ENABLED=0
RERANK_URL=https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank
RERANK_MODEL=gte-rerank-v2
RERANK_API_KEY=

# ── 运行模式 ──
MOCK=0

# ── 路径与检索参数 ──
CHROMA_DIR=data/chroma
RAW_DIR=data/raw
CHUNKS_FILE=data/chunks.jsonl
COLLECTION=doc_qa
TOP_K_VEC=10
TOP_K_BM25=10
TOP_K_FINAL=4
CHUNK_SIZE=400
CHUNK_OVERLAP=50
```

`.env.example` 的内容 = 上面这段（`LLM_API_KEY` / `EMBED_API_KEY` 留空）。
`.gitignore` 必须包含：`.env`、`.venv/`、`__pycache__/`、`*.pyc`、`data/chroma/`、`data/chunks.jsonl`、`data/raw/*`（但用 `!data/raw/README.md` 放行说明文件）、`eval/report*.json`。

---

## 4. 数据格式（冻结）

### `data/chunks.jsonl`（ingest 产出，一行一个 chunk）
```json
{"id":"服务说明.md#0000","text":"...","source":"服务说明.md","heading":"一、订单状态","index":0}
```

### `eval/questions.jsonl`（用户出题，一行一题）
```json
{"id":"q01","type":"single_hop","question":"订单从待支付到服务中要经过哪些状态？","gold":"待支付→已支付→待接单→已接单→服务中","keypoints":["待支付","已支付","待接单","已接单","服务中"],"gold_sources":["01_订单状态机.md"],"must_refuse":false}
```
- `type` ∈ `single_hop` | `multi_hop` | `unanswerable`
- `must_refuse=true` 的题，`gold_sources` 可为 `[]`
- `eval/questions.example.jsonl` 放 **2 条纯示例**（内容是占位说明，不指向真实语料），用户复制成 `eval/questions.jsonl` 再改。

---

## 5. 冻结接口

### `src/config.py`
```python
PROJECT_ROOT: Path          # = rag-doc-qa/ 的绝对路径（由 __file__ 上溯两级）

@dataclass(frozen=True)
class Settings:
    llm_base_url: str; llm_api_key: str; llm_model: str
    embed_base_url: str; embed_api_key: str; embed_model: str
    embed_dim: int; embed_batch: int
    rerank_enabled: bool; rerank_url: str; rerank_model: str; rerank_api_key: str
    mock: bool
    chroma_dir: Path; raw_dir: Path; chunks_file: Path; collection: str
    top_k_vec: int; top_k_bm25: int; top_k_final: int
    chunk_size: int; chunk_overlap: int

def load_settings(env_file: Path | None = None) -> Settings
```
- 读取 `PROJECT_ROOT/.env`（不存在则跳过）：忽略空行与 `#` 开头；`KEY=VALUE` 按第一个 `=` 切分；值两端引号剥除。
- **环境变量优先级高于 .env 文件**（`os.environ` 覆盖）。
- 上面表格里的默认值就是兜底值；缺 key 时用默认值，**不得抛异常**。
- 布尔解析：`1/true/yes/on`（忽略大小写）=True，其余 False。
- 路径字段：相对路径一律 `PROJECT_ROOT / 值` 解析为绝对路径。
- 若 `python-dotenv` 可导入则用它读，否则用手写解析（两种结果必须一致）。

### `src/chunking.py`（纯标准库）
```python
@dataclass(frozen=True)
class Chunk:
    id: str; text: str; source: str; heading: str; index: int
    def to_dict(self) -> dict
    @staticmethod
    def from_dict(d: dict) -> "Chunk"

def normalize(text: str) -> str
def split_text(text: str, source: str, size: int = 400, overlap: int = 50) -> list[Chunk]
```
`normalize`：`\r\n`/`\r` → `\n`；去行尾空白；连续空行压成 1 个空行；`strip()` 整体。
`split_text` 契约：
- 空串或纯空白 → `[]`。
- markdown 标题行（`^#{1,6}\s`）是**硬边界**：标题变化时结束当前 chunk（当前 chunk 为空则直接开新 chunk）；`heading` = 最近一次标题文本（去掉 `#` 与首尾空白），无标题时为 `""`。
- 其余内容按**空行分隔的段落**装箱：累加到不超过 `size` 字符；单段超过 `size` 时按 `size` 硬切（不丢字符）。
- 相邻 chunk 重叠：新 chunk 以「上一个 chunk 末尾 `overlap` 个字符」为前缀，**仅在不跨标题边界时**；重叠后仍不得超过 `size + overlap`。
- `id = f"{source}#{index:04d}"`，`index` 从 0 连续递增。
- 每个 chunk 的 `text` 必须非空（`strip()` 后）。
- 确定性：同一输入两次调用，返回的 id / text 完全一致。
- `overlap >= size` 时把 overlap 视作 `size // 4`，不得死循环。

### `src/fusion.py`（纯标准库）
```python
@dataclass(frozen=True)
class Hit:
    chunk_id: str; text: str; source: str; heading: str
    score: float; retriever: str      # "vector" | "bm25" | "fused" | "rerank"

def rrf_fuse(rankings: dict[str, list[str]], k: int = 60) -> list[tuple[str, float]]
def dedupe_keep_order(items: list[str]) -> list[str]
```
`rrf_fuse`：`score = Σ_retriever 1/(k + rank)`，rank 从 **1** 开始；按 score 降序，**score 相同时按 chunk_id 字典序升序**（保证确定性）；空输入 → `[]`；同一 list 内重复 id 只计首次出现的 rank。

### `src/embed.py`
```python
class Embedder:
    def __init__(self, settings: Settings) -> None
    def embed_texts(self, texts: list[str]) -> list[list[float]]
    def embed_query(self, text: str) -> list[float]

class MockEmbedder:      # 同签名
    def __init__(self, settings: Settings) -> None
    ...

def get_embedder(settings: Settings) -> Embedder | MockEmbedder
```
- `get_embedder`：`settings.mock` 为真返回 `MockEmbedder`，否则 `Embedder`。
- `Embedder.__init__` 内延迟 `from openai import OpenAI`；`OpenAI(base_url=..., api_key=...)`；`api_key` 为空 → `RuntimeError("EMBED_API_KEY 未配置")`。
- `embed_texts`：空列表 → `[]`；按 `settings.embed_batch` 分批调用 `client.embeddings.create(model=..., input=batch)`；返回顺序必须与输入一致（用 `resp.data[i].index` 重排）；请求失败重试 1 次后 `RuntimeError`。
- `MockEmbedder`（纯标准库，离线）：`hashlib` 对字符 1-gram + 2-gram 做哈希落到 `settings.embed_dim` 个桶计数，再做 L2 归一化。要求：① 相同输入结果恒等；② **共享字词多的两个输入余弦相似度明显更高**；③ 不得返回全零向量（全零时把第 0 维置 1.0）。

### `src/store.py`
```python
class VectorStore:
    def __init__(self, settings: Settings) -> None
    def reset(self) -> None
    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int
    def query(self, embedding: list[float], top_k: int) -> list[Hit]
    def count(self) -> int
    def all_chunks(self) -> list[Chunk]
```
- `import chromadb` 只在 `__init__` 内；`chromadb.PersistentClient(path=str(settings.chroma_dir))`；`get_or_create_collection(name=settings.collection, metadata={"hnsw:space": "cosine"})`。
- **严禁使用 chromadb 默认 embedding function**（会联网下载 ONNX 模型）：必须显式传 `embeddings=` 与 `query_embeddings=`。
- `upsert`：`ids` / `documents` / `metadatas({"source","heading","index"})` / `embeddings` 四者等长；`chunks` 与 `embeddings` 长度不等 → `ValueError`；返回写入条数。
- `query`：返回 `Hit(retriever="vector", score=1.0 - distance)`；`text`/`source`/`heading` 从 `include=["documents","metadatas","distances"]` 取；结果按 score 降序。
- `count()`：collection 条数。
- `all_chunks()`：**从 `settings.chunks_file` 读 jsonl**（权威来源），文件不存在 → `[]`；坏行跳过。

### `src/bm25.py`
```python
class KeywordIndex:
    def __init__(self, chunks: list[Chunk]) -> None
    @classmethod
    def from_chunks_file(cls, path: Path) -> "KeywordIndex"
    def search(self, query: str, top_k: int) -> list[Hit]
    def size(self) -> int
```
- `jieba` / `rank_bm25` 延迟导入；分词 `[t for t in jieba.lcut(query) if t.strip()]`。
- 空 index 或空 query → `[]`；返回 `Hit(retriever="bm25", score=BM25 原始分)`，按 score 降序，最多 `top_k` 条。
- `from_chunks_file`：读 jsonl（坏行跳过），文件不存在 → 空索引（不抛异常）。

### `src/retrieve.py`
```python
class Retriever:
    def __init__(self, settings: Settings) -> None
    def search(self, question: str, top_k: int | None = None, use_rerank: bool | None = None) -> list[Hit]
    def debug(self, question: str) -> dict    # {"vector":[id...],"bm25":[id...],"fused":[id...],"final":[id...]}
```
- 流程：`vector top_k_vec` + `bm25 top_k_bm25` → `rrf_fuse` → 取 `top_k_final`（`top_k` 参数覆盖）。
- 融合后需要把 id 还原成完整 `Hit`：以 `VectorStore.all_chunks()` 建的 `{id: Chunk}` 映射为准；映射里找不到的 id 直接丢弃。
- `use_rerank` 默认取 `settings.rerank_enabled`；rerank 只在 `not settings.mock` 时真正调用。**rerank 任何异常都必须吞掉并降级为融合结果**（可 `print` 一行 warning），绝不允许因 rerank 失败让问答报错。
- rerank 请求用 `requests`（延迟导入），`POST settings.rerank_url`，body 形如
  `{"model": ..., "input": {"query": question, "documents": [text...]}, "parameters": {"top_n": top_k_final}}`，
  header `Authorization: Bearer {rerank_api_key or embed_api_key}`；解析 `output.results[i].index` 与 `.relevance_score`；解析失败即降级（字段名以官方文档为准，代码注释里注明这一条）。
- `question` 为空 → 返回 `[]`。

### `src/generate.py`
```python
@dataclass
class Answer:
    text: str; citations: list[str]; latency_ms: int; prompt_chars: int; mocked: bool

def build_prompt(question: str, hits: list[Hit], max_chars: int = 3000) -> str

class Generator:
    def __init__(self, settings: Settings) -> None
    def answer(self, question: str, hits: list[Hit]) -> Answer

class MockGenerator:      # 同签名
    ...

def get_generator(settings: Settings) -> Generator | MockGenerator
```
`build_prompt` 硬要求：
- 指令段必须包含：**"仅依据【资料】回答；资料中未包含的信息，必须回答「根据现有资料无法回答」；不得编造出处；回答末尾用 `[编号]` 列出实际用到的资料"**。
- 每条资料格式：`[{i}] 来源：{source} > {heading}\n{text}`，`i` 从 1 开始。
- 总长度超 `max_chars` 时按顺序截断，但**至少保留 1 条资料**。
- `hits` 为空 → 返回仍然合法的 prompt，其中资料区写明"（无可用资料）"。
- `Generator`：`openai` 延迟导入，`temperature=0`，`timeout=60`；失败重试 1 次后 `RuntimeError`；`citations` 从回答文本里正则抽出 `[数字]` 去重后按数字升序。
- `MockGenerator`：**不联网**；`hits` 为空 → `text="根据现有资料无法回答"`、`citations=[]`；否则取 `hits[0].text` 第一句作答案并附 `[1]` 引用；`mocked=True`。

### `src/ingest.py`
```python
@dataclass
class RawDoc:
    source: str; text: str

def read_raw_files(raw_dir: Path) -> list[RawDoc]
def run_ingest(settings: Settings, reset: bool = True) -> dict
```
- `read_raw_files`：遍历 `raw_dir` 下 `*.md` / `*.txt`（utf-8，`errors="replace"`）与 `*.pdf`（`pypdf` 延迟导入，逐页 `extract_text()` 拼接）；`source` = 文件名（不含目录）；跳过抽不出文本的文件并 print 警告；按文件名排序返回。
- `run_ingest`：读取 → `split_text`（用 `settings.chunk_size` / `chunk_overlap`）→ 写 `settings.chunks_file`（父目录自动创建，`ensure_ascii=False`）→ embedding → `store.reset()`（`reset=True` 时）+ `upsert`。
- 返回 `{"files": int, "chunks": int, "sources": [str...], "elapsed_ms": int, "mocked": bool}`。
- 语料为空：不抛异常，返回 `chunks=0` 并 print 明确警告 `[warn] data/raw 下没有可入库文档`。

### `eval/metrics.py`（纯标准库）
```python
def normalize_answer(s: str) -> str
def exact_match(pred: str, gold: str) -> bool
def contains_match(pred: str, gold: str) -> bool
def keypoints_match(pred: str, keypoints: list[str]) -> float     # 命中比例 0..1
def score_answer(pred: str, gold: str, keypoints: list[str], must_refuse: bool) -> str
def hit_at_k(retrieved_ids: list[str], gold_sources: list[str], k: int) -> bool
def citation_hit(citations: list[str], gold_sources: list[str]) -> bool
def aggregate(records: list[dict]) -> dict
```
- `normalize_answer`：`lower()`、全角转半角、去所有空白、去 `，。、；：？！,.;:?!()（）[]【】"'` 等标点。
- `score_answer`：`must_refuse=True` → 预测含 `无法回答` / `没有相关` / `资料中未` / `未提及` 任一 → `"correct"`，否则 `"wrong"`；否则 `keypoints_match >= 0.8` 或 `exact_match` → `"correct"`；`> 0` 或 `contains_match` → `"partial"`；其余 `"wrong"`。
- `hit_at_k`：`gold_sources` 中任一文件名出现在 `retrieved_ids[:k]` 的 chunk_id 前缀里 → True；`gold_sources` 为空 → False。
- `aggregate(records)` 返回
  `{"n":int, "accuracy":float, "partial_rate":float, "wrong_rate":float, "refusal_accuracy":float, "hit_rate":float}`（`accuracy` = correct 占比；`hit_rate` = `hit` 为真的占比；除零时返回 0.0）。

### `eval/run_eval.py`
命令行：
```
python -m eval.run_eval --mode retrieval|full|mock --questions eval/questions.jsonl --out eval/report.json [--limit N] [--top-k K]
```
- 读 jsonl（坏行跳过）；题库为空 → 打印错误并以退出码 **1** 结束。
- `--mode retrieval`：只跑检索，`pred=""`；`--mode full`：检索 + 生成；`--mode mock`：`Settings(mock=True)` 走 MockEmbedder + MockGenerator（**不需要 API key、不需要网络**，但仍需 chromadb）。
- 每条记录输出：`{id, type, question, pred, gold, score, retrieved_ids[:k], hit, citation_hit, latency_ms}`。
- 结束打印并写 JSON：`n / accuracy / partial_rate / wrong_rate / refusal_accuracy / hit_rate / avg_latency_ms`（用 `aggregate`）。

### `app/main.py`（FastAPI）
```
GET  /health   -> {"status":"ok","mock":bool,"chunks":int}
POST /ingest   body {"reset": true} -> run_ingest 结果
POST /chat     body {"question": str, "top_k": int|null}
               -> {"answer": str, "citations": [str], "hits": [{"chunk_id","source","heading","score","retriever"}], "latency_ms": int, "mocked": bool}
```
- 启动时不建索引（lazy）；`/chat` 首次调用时构建 `Retriever` / `Generator` 并缓存。
- `question` 为空或非字符串 → HTTP **400**。
- 检索结果为空时仍走生成，返回"根据现有资料无法回答"级别的结果，不报 500。
- 入口：`if __name__ == "__main__": uvicorn.run("app.main:app", host="127.0.0.1", port=8000)`（`uvicorn` 延迟导入，或顶层 import 也可，因为该文件不参与离线单测）。

### `tests/test_offline.py`（纯标准库，**不得** import chromadb/openai/fastapi/jieba/rank_bm25/pypdf/requests）
用 `unittest`，至少覆盖：
1. `split_text`：空输入→`[]`；小文档单 chunk；长文档每块 `len(text) <= size + overlap`；覆盖全部非空段落文字；id 连续且形如 `source#0000`；跨标题边界不重叠且 `heading` 正确；两次调用结果一致。
2. `rrf_fuse`：手算 2 路 3 条 id 的期望顺序；score 相同按 id 升序；空输入→`[]`；`dedupe_keep_order` 保持首次出现顺序。
3. `metrics`：`normalize_answer` 全角/标点/大小写；`keypoints_match` 命中比例；`score_answer` 四分支（含 `must_refuse`）；`hit_at_k` 的 k 边界；`aggregate` 的除零。
4. `load_settings`：`.env` 覆盖默认值、`os.environ` 覆盖 `.env`、布尔与整数解析、相对路径解析成绝对路径。
5. `MockEmbedder`：相同输入恒等；两个共享字词多的输入余弦相似度 > 两个无关输入的相似度；向量非全零、维度 = `embed_dim`；`get_embedder(mock=True)` 返回 `MockEmbedder`。
6. `Chunk.to_dict/from_dict` 往返一致。

---

## 6. 验收命令（本机绝对路径，沙箱内 PATH 为空）

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"

# 语法检查（全部卡都必须过）
& $P -m compileall -q $R

# 离线单测（无第三方依赖，必须全绿）
& $P -m unittest discover -s "$R\tests" -t $R -v
```

单卡验收命令 = `py_compile` 自己负责的文件；全局验收由 captain 在全部卡落地后执行。

---

## 7. 语料说明

`data/raw/` 放 10 份文档（建议）：
1. 保洁系统：需求说明、数据库设计、接口文档、部署文档、订单状态机说明（用户自己项目的文档）
2. 框架官方中文文档：Spring Boot、MyBatis-Plus、Vue 3、MySQL/Redis 相关章节
3. 种子文件：`00_保洁系统_项目说明.md`（captain 已从 `简历用图/README_简历配图说明.md` 复制而来，用于立刻跑通链路）

`docs/DOC_SOURCES.md` 列出建议文档的**来源 URL**（供用户手动下载），并注明"具体地址以官方文档为准"。
