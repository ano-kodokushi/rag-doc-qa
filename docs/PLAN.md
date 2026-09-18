# 执行计划书 · PLAN

> 把 `SPEC.md` 拆成 Agent 能一口吃掉、且**每张卡都能独立验收**的小块。
> 优先级：`SPEC.md` > `AGENTS.md` > 本文件。
> 粒度铁律：**一张卡要能在一次会话内做完并验证**。做不完说明还能再拆。

## 0. 拆分原则

1. 单卡改动文件 ≤ 3 个
2. 每张卡必须有**可复制执行的验收命令** + **可判定的通过标准**（数字、退出码、行数）
3. 依赖写成 DAG，不允许循环依赖
4. **每张卡自带结论模板**——答不出模板里的空，就不算完成
5. 写不出验收命令的卡 = 还没想清楚，回去重拆

## 0.1 现状盘点（2026-09-18 实测，拆卡依据）

| 项 | 状态 |
|---|---|
| `src/` 9 个模块 + `eval/` + `app/` | **已实现**，无 TODO/占位 |
| 离线单测 | **23 项全绿**，覆盖 `SPEC.md §5` 全部 6 类契约 |
| `compileall` | 通过（退出码 0） |
| 第三方依赖 | ❌ **`chromadb` / `openai` / `fastapi` / `jieba` / `rank_bm25` / `uvicorn` / `dotenv` 均未安装**（仅 `pypdf`、`requests` 已装） |
| `eval/questions.jsonl` | ❌ **不存在**（只有 `questions.example.jsonl`） |
| `data/raw/` 语料 | ⚠️ 只有 1 份种子文件（`SPEC.md §7` 建议 10 份） |
| `.env` | ❌ 不存在（只有 `.env.example`） |
| 真实检索 / 生成 | ❌ **从未跑过** |

**结论：缺的不是"写代码"，是"装依赖 → 出题 → 真跑 → 拿到真实数字"。**
所以卡分两类：**离线可验收（T-004 ~ T-007）** 与 **需要凭据才能验收（T-008 ~ T-009）**。

## 0.2 硬约束（每张卡都要遵守，违反即 reject）

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"   # 唯一允许的解释器
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
$K = "C:\Users\a2695\Desktop\作业\Agent\_kit_inspect\agent-project-kit\push-task.mjs"   # 治理套件脚本，不在仓库内，禁止用相对路径
```

- ❌ 机器上另有 **Anaconda Python 3.7**（`C:\Users\a2695\anaconda3\python.exe`）—— **绝对禁止使用**
- 沙箱内 `PATH` 为空串，`python` / `node` / `git` **一律写绝对路径**
- 第三方库**只能延迟导入**（例外：`app/main.py` 可顶层 `from fastapi import FastAPI`）
- **不得修改 `SPEC.md`**；不得超出各卡 `inScope`
- **`docs/BOARD.md` 是跨卡共享状态文件**：即使某卡把 `docs/**` 列为 outOfScope，本卡也**必须**更新它——`AGENTS.md §8` 的 DoD 强制要求「BOARD 状态已更新」，这是 outOfScope 的**唯一例外**（T-011 修）

---

## 1. 里程碑 M1 · 跑通（不花一分钱）

> 目标：在 `MOCK=1` 模式下把「入库 → 检索 → 生成 → 评测」整条链路跑通。
> **不需要 API key、不联网。** 这是唯一能立刻证明"这项目真的能跑"的路径。

| ID | 任务 | 依赖 | 档位 | 状态 |
|---|---|---|---|---|
| T-004 | 安装依赖并冻结环境 | — | T2 | **完成** |
| T-005 | 建 20 题题库文件（占位可直接跑） | T-004 | T2 | **完成** |
| T-006 | 补齐语料至 10 份 | — | T2 | **完成** |
| T-007 | mock 模式全链路验收（核心卡） | T-004, T-005, T-006 | T1 | **完成**（2026-09-18） |

> **M1 已闭环**：`MOCK=1` 下「入库 → 检索 → 生成 → 评测」全链路跑通，零 API key、零费用。

## 2. 里程碑 M2 · 真实数字

| ID | 任务 | 依赖 | 档位 | 状态 |
|---|---|---|---|---|
| T-008 | 按真实语料出 20 题正式题库 | T-006 | T1 | **完成** |
| T-009 | 真实模式 20 题评测，产出报告 | T-007, T-008 | T1 | **完成**（2026-09-18） |
| T-010 | 文档与交接收口 | T-009 | T2 | **完成**（2026-09-18） |

> **M2 已拿到真实数字**（**最终语料**：12 份 / 400 块，`eval/report.json`）：
> `{n:20, accuracy:0.45, partial_rate:0.30, wrong_rate:0.25, refusal_accuracy:1.00, hit_rate:0.80, avg_latency_ms:1654.6}`
> **引用时务必注明"单次运行"** —— 同参数连跑，`accuracy` 实测落在 0.45–0.50（见 §5.5）。
> 该数字已按最终语料**刷新过一次**：T-012 去掉 `README.md` 噪声前后各测一遍作对照（见 §5.9）。

## 2.5 里程碑 M3 · 治理链修复（可与其他卡并行）

| ID | 任务 | 依赖 | 档位 | 状态 |
|---|---|---|---|---|
| T-011 | 补齐 TASK_BRIEF 并修掉治理矛盾 | — | L1 / T1 | **完成** |

## 2.6 里程碑 M4 · 缺陷修复（可与其他卡并行）

| ID | 任务 | 依赖 | 档位 | 状态 |
|---|---|---|---|---|
| T-012 | 排除 README 等说明文件被当作语料入库 | — | L1 / T1 | **完成** |
| T-013 | 让离线单测对环境变量隔离（MOCK 泄漏导致假失败） | — | L1 / T1 | **完成** |
| T-014 | `/chat` 的 `latency_ms` 只覆盖生成段，不含检索与冷启动 | — | L1 / T1 | **完成** |

> **M4 全部闭环**：T-012 / T-013 / T-014 均已修复并推送。**全项目 14 / 14 卡片完成，零待办。**

**DAG**

```
T-004 ─┬─→ T-005 ─┐
       │          ├─→ T-007 ─→ T-009 ─→ T-010
T-006 ─┴──────────┘        ↗
       └─→ T-008 ──────────
```

---

# 任务卡

## T-004 · 安装依赖并冻结环境

| | |
|---|---|
| **难度 / 档位** | L0 / T2 |
| **依赖** | — |
| **inScope** | `requirements.txt`（仅在确实需要改依赖时） |
| **outOfScope** | `SPEC.md`、`src/**`、`eval/**`、`docs/**` |

**goal**：让 `requirements.txt` 里声明的第三方库在**指定解释器**下可导入，并记录实际版本。

**为什么必须**：当前 `chromadb` / `openai` / `fastapi` / `jieba` / `rank_bm25` / `uvicorn` / `dotenv` 全部缺失，任何集成验收都跑不了。

**验收命令**

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"

# 1) 安装
& $P -m pip install -r "$R\requirements.txt"

# 2) 逐个确认可导入（9 个全 YES）
& $P -c "import importlib.util as u; mods=['chromadb','openai','fastapi','jieba','rank_bm25','pypdf','requests','uvicorn','dotenv']; [print(m, 'YES' if u.find_spec(m) else 'NO') for m in mods]"

# 3) 确认装的是 3.12 而不是 Anaconda 3.7
& $P -c "import sys; print(sys.version); print(sys.executable)"

# 4) 离线单测仍全绿（装依赖不能弄坏已有契约）
& $P -m unittest discover -s "$R\tests" -t "$R"
```

**通过标准**
- `mods` 那 9 个**全部 `YES`**
- `sys.version` 以 `3.12` 开头，`sys.executable` 指向 `...\Programs\Python\Python312\python.exe`
- 单测 `OK`（不少于 23 项）

**结论模板**

```
任务：T-004 安装依赖
改动文件：requirements.txt（若改）
验收结果：
  [x] 9 个模块导入检查 —— 实际输出：<粘贴>
  [x] 解释器确认 —— 实际：<粘贴 sys.version / sys.executable>
  [x] 离线单测 —— 实际：Ran N tests, OK
遗留问题：<无 / 具体描述>
```

**卡住时**：装 `chromadb` 若拉取慢或失败 → 记录 pip 原始报错与已试过什么，写进 `docs/BOARD.md` 阻塞区，**不要硬扛超过 2 次**。

---

## T-005 · 建 20 题题库文件

| | |
|---|---|
| **难度 / 档位** | L0 / T2 |
| **依赖** | T-004 |
| **inScope** | `eval/questions.jsonl` |
| **outOfScope** | `eval/questions.example.jsonl`、`eval/README.md`、`src/**`、`SPEC.md` |

**goal**：产出 `eval/questions.jsonl`，20 题，格式与配比符合 `eval/README.md`。

**本卡定位**：这是**结构占位题库**——目的是让链路先跑起来；题目内容由 T-008 换成真实语料的正式题。
所以本卡验收**只查格式与配比，不查题目质量**。

**格式（`SPEC.md §4`）**

```json
{"id":"q01","type":"single_hop","question":"...","gold":"...","keypoints":["..."],"gold_sources":["..."],"must_refuse":false}
```

**配比（`eval/README.md §1`，不得随意改）**

| `type` | 题数 |
|---|---|
| `single_hop` | 12 |
| `multi_hop` | 5 |
| `unanswerable` | 3 |
| **合计** | **20** |

**验收命令**

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"

# 1) 行数 = 20
(Get-Content "$R\eval\questions.jsonl").Count

# 2) 合法 JSON + 必备字段 + 配比 + id 唯一 + must_refuse 一致
& $P -c @"
import json,collections
rows=[json.loads(l) for l in open(r'$R\eval\questions.jsonl',encoding='utf-8') if l.strip()]
req={'id','type','question','gold','keypoints','gold_sources','must_refuse'}
print('n =',len(rows))
print('缺字段:',[r.get('id') for r in rows if not req<=set(r)])
print('配比 =',dict(collections.Counter(r['type'] for r in rows)))
print('id 唯一 =',len({r['id'] for r in rows})==len(rows))
print('must_refuse 一致 =',all(r['must_refuse']==(r['type']=='unanswerable') for r in rows))
"@

# 3) 必须是中文直写，不能是 \uXXXX 转义
Select-String -Path "$R\eval\questions.jsonl" -Pattern '\\u' | Measure-Object | Select-Object -ExpandProperty Count
```

**通过标准**
- 第 1 条输出 **20**
- `缺字段: []`、`配比` 恰好 `{'single_hop':12,'multi_hop':5,'unanswerable':3}`、`id 唯一 = True`、`must_refuse 一致 = True`
- 第 3 条输出 **0**（无 `\uXXXX` 转义）

**结论模板**

```
任务：T-005 建题库
改动文件：eval/questions.jsonl
验收结果：
  [x] 行数 —— 实际：20
  [x] 字段/配比/唯一性 —— 实际输出：<粘贴>
  [x] 无 unicode 转义 —— 实际：0
遗留问题：<无>
```

---

## T-006 · 补齐语料至 10 份

| | |
|---|---|
| **难度 / 档位** | L0 / T2（人工为主） |
| **依赖** | — |
| **inScope** | `data/raw/**`、`docs/DOC_SOURCES.md` |
| **outOfScope** | `src/**`、`eval/questions.jsonl`、`SPEC.md` |

**goal**：`data/raw/` 下 `.md` / `.txt` / `.pdf` 达到 **10 份**，并在 `docs/DOC_SOURCES.md` 登记来源。

**本卡是人工卡**：`SPEC.md §7` 说明语料由用户提供，**代码不得硬编码语料内容**。
Agent 能做的是核对数量、核对命名、更新 `DOC_SOURCES.md`。

**验收命令**

```powershell
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
(Get-ChildItem "$R\data\raw" -File -Include *.md,*.txt,*.pdf -Recurse |
   Where-Object { $_.Name -ne 'README.md' }).Count
Get-ChildItem "$R\data\raw" -File | Select-Object Name,Length
```

**通过标准**
- 语料文件数（**不含 `README.md`**）≥ **10**
- `README.md` 必须仍在（`.gitignore` 用 `!data/raw/README.md` 放行它）

**结论模板**

```
任务：T-006 补齐语料
改动文件：data/raw/*（新增语料）、docs/DOC_SOURCES.md
验收结果：
  [x] 语料数 —— 实际：N 份（列出文件名）
  [x] README.md 仍在 —— 是
遗留问题：<缺哪几份 / 无>
```

**卡住时**：语料需要用户下载 → **如实记为阻塞**，不要用假文件凑数（那会让 T-009 的数字失真）。

---

## T-007 · mock 模式全链路验收 ★核心卡

| | |
|---|---|
| **难度 / 档位** | L1 / T1 |
| **依赖** | T-004, T-005, T-006 |
| **inScope** | 无（本卡**只验收不改代码**；发现问题开新卡） |
| **outOfScope** | `src/**`、`eval/**`、`SPEC.md` |

**goal**：证明「入库 → 检索 → 生成 → 评测」在 `MOCK=1` 下真的能跑通，并拿到可读的数字。

**为什么是核心卡**：这是**唯一不需要 API key、不需要联网**就能证明项目可用的路径。
它一旦通过，剩下的只是换凭据。

**验收命令**（逐条执行，全部要留原始输出）

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Set-Location $R
$env:MOCK = "1"     # 环境变量优先级高于 .env（SPEC.md §5）

# 1) 入库（mock embedding，不联网）
& $P -m src.ingest
"ingest exit=$LASTEXITCODE"

# 2) 产物存在
"chunks.jsonl = $(Test-Path "$R\data\chunks.jsonl")"
(Get-Content "$R\data\chunks.jsonl").Count
"chroma 目录 = $(Test-Path "$R\data\chroma")"

# 3) 20 题评测（mock 模式）
& $P -m eval.run_eval --mode mock --questions eval\questions.jsonl --out eval\report_mock.json
"eval exit=$LASTEXITCODE"

# 4) 报告可读
Get-Content "$R\eval\report_mock.json" | Select-Object -First 20
```

**通过标准**（逐条对照，不许"看着差不多"）
- 第 1 条 `ingest exit=0`，输出里 `files` ≥ 10、`chunks` > 0、`mocked=true`
- 第 2 条 `chunks.jsonl = True` 且行数 = 上一步的 `chunks`；`chroma 目录 = True`
- 第 3 条 `eval exit=0`，且**不出现任何网络请求 / API key 报错**
- 第 4 条 JSON 含 `n=20` 与 `accuracy / hit_rate / avg_latency_ms` 等键

**反作弊探针（必做一次）**
另存一份只有 3 题的题库（如 `eval/questions.probe.jsonl`），重跑第 3 条，
确认 `n` 随之变成 **3** 而不是 20——证明它真的在读 `--questions` 指向的文件。

**结论模板**

```
任务：T-007 mock 全链路
改动文件：无（只验收）；产物 data/chunks.jsonl、data/chroma、eval/report_mock.json
验收结果：
  [x] ingest 退出码 0，files=N chunks=M mocked=true —— 原始输出：<粘贴>
  [x] chunks.jsonl 行数 = M，chroma 目录存在 —— 实际：<粘贴>
  [x] eval 退出码 0，无网络/凭据报错 —— 原始输出：<粘贴>
  [x] report_mock.json 含 n=20 与指标键 —— 实际：<粘贴>
  [x] 反作弊探针：3 题题库 -> n=3 —— 实际：<粘贴>
遗留问题：<无 / 具体描述>
```

**卡住时**：这是**集成卡**，可能暴露真 bug。规则：
1. 先判断是**环境问题**（依赖没装好）还是**代码问题**
2. 是代码问题 → **不要在本卡里改**，记下最小复现，开新卡（本卡 inScope 为空）
3. 同一问题失败超过 2 次 → 停止，写 `docs/BOARD.md` 阻塞区

---

## T-008 · 按真实语料出 20 题正式题库

| | |
|---|---|
| **难度 / 档位** | L1 / T1 |
| **依赖** | T-006 |
| **inScope** | `eval/questions.jsonl` |
| **outOfScope** | `eval/questions.example.jsonl`、`src/**`、`SPEC.md` |

**goal**：把 T-005 的占位题换成**基于 `data/raw/` 真实语料**的 20 题；`gold_sources` 必须指向真实存在的文件名。

**验收命令**

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"

# 1) 配比与格式
& $P -c @"
import json,collections
rows=[json.loads(l) for l in open(r'$R\eval\questions.jsonl',encoding='utf-8') if l.strip()]
print('n =',len(rows)); print('配比 =',dict(collections.Counter(r['type'] for r in rows)))
"@

# 2) 关键：gold_sources 必须都是 data/raw 下真实存在的文件
& $P -c @"
import json,os
R=r'$R'
rows=[json.loads(l) for l in open(os.path.join(R,'eval','questions.jsonl'),encoding='utf-8') if l.strip()]
have=set(os.listdir(os.path.join(R,'data','raw')))
print('引用了不存在的文件:',sorted({s for r in rows for s in r['gold_sources'] if s not in have}))
print('unanswerable 题为空 sources =',all(r['gold_sources']==[] for r in rows if r['type']=='unanswerable'))
"@
```

**通过标准**
- 配比仍为 `12 / 5 / 3`
- `引用了不存在的文件: []`
- `unanswerable 题为空 sources = True`

**结论模板**

```
任务：T-008 正式题库
改动文件：eval/questions.jsonl
验收结果：
  [x] 配比 12/5/3 —— 实际：<粘贴>
  [x] gold_sources 全部真实存在 —— 实际：引用了不存在的文件: []
  [x] unanswerable 的 sources 为空 —— 实际：True
遗留问题：<无法覆盖的题型 / 无>
```

---

## T-009 · 真实模式 20 题评测

| | |
|---|---|
| **难度 / 档位** | L1 / T1 |
| **依赖** | T-007, T-008 |
| **inScope** | `eval/report.json`（产物）、`docs/BOARD.md` |
| **outOfScope** | `src/**`、`eval/questions.jsonl`、`SPEC.md` |

**goal**：在**非 mock** 模式下跑完 20 题，产出 `eval/report.json`，并把**真实数字**记进 `docs/BOARD.md`。

**前置（需要用户提供）**：`$R\.env` 里填好 `LLM_API_KEY` 与 `EMBED_API_KEY`；依赖已装（T-004）。

**验收命令**

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Set-Location $R
$env:MOCK = "0"

# 1) 真入库（会真的调 Embedding 接口，产生费用）
& $P -m src.ingest
"ingest exit=$LASTEXITCODE"

# 2) 20 题真实评测
& $P -m eval.run_eval --mode full --questions eval\questions.jsonl --out eval\report.json
"eval exit=$LASTEXITCODE"

# 3) 报告指标
Get-Content "$R\eval\report.json"
```

**通过标准**
- 两条命令退出码均为 **0**
- `report.json` 含 `n=20` 与 `accuracy / partial_rate / wrong_rate / refusal_accuracy / hit_rate / avg_latency_ms`
- `docs/BOARD.md` 里记的是 `report.json` 的**真实数值**，不许四舍五入到好看、不许只挑好指标

**红线（本卡最容易犯）**
- ❌ 指标难看就改题、改 `keypoints`、改 `gold` 让分数变高 → **作废重来**
- ❌ 只报 `accuracy` 不报 `wrong_rate` / `refusal_accuracy` → 视为未完成
- ❌ 接口失败就谎报成功 → 按 `AGENTS.md §7.8` 记失败并写阻塞

**结论模板**

```
任务：T-009 真实评测
改动文件：eval/report.json、docs/BOARD.md
验收结果：
  [x] ingest 退出码 0 —— 原始输出：<粘贴>
  [x] eval 退出码 0 —— 原始输出：<粘贴>
  [x] report.json 指标 —— n=20 accuracy=? partial_rate=? wrong_rate=? refusal_accuracy=? hit_rate=? avg_latency_ms=?
  [x] BOARD.md 已记入上述原始数值 —— 是
遗留问题：<哪类题最差、疑似原因>
```

---

## T-010 · 文档与交接收口

| | |
|---|---|
| **难度 / 档位** | L0 / T2 |
| **依赖** | T-009 |
| **inScope** | `README.md`、`docs/BOARD.md`、`docs/PLAN.md` |
| **outOfScope** | `SPEC.md`、`src/**`、`eval/**` |

**goal**：让下一个会话能无缝接续——把实际跑通的命令、真实数字、已知限制写清楚。

**验收命令**

```powershell
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
# README 里的命令必须真的跑得通（本轮实际执行过）
Select-String -Path "$R\README.md" -Pattern '\$P -m' | ForEach-Object { $_.Line.Trim() }
# BOARD 里不能留「待办」却其实已经做完的卡
Select-String -Path "$R\docs\BOARD.md" -Pattern '待办'
```

**通过标准**
- `README.md` 里每条 `$P -m ...` 命令**本轮都实际执行过**，结果已记录
- `docs/BOARD.md` 进度表与实际一致（不许留"待办"却已完成的卡）
- 交接记录含：已跑通的命令、真实数字、已知限制、下一步

**结论模板**

```
任务：T-010 收口
改动文件：README.md、docs/BOARD.md、docs/PLAN.md
验收结果：
  [x] README 命令逐条实跑 —— 实际：<哪几条、什么结果>
  [x] BOARD 状态与实际一致 —— 是
  [x] 交接记录含数字与限制 —— 是
遗留问题：<无>
```

---

## T-011 · 补齐 TASK_BRIEF 并修掉治理矛盾

| | |
|---|---|
| **难度 / 档位** | L1 / T1 |
| **依赖** | — |
| **inScope** | `docs/TASK_BRIEF.md`、`docs/PLAN.md`、`docs/BOARD.md` |
| **outOfScope** | `SPEC.md`、`AGENTS.md`、`README.md`、`src/**`、`eval/**` |

**goal**：让治理链不再断在第一环——`AGENTS.md §1` 把 `docs/TASK_BRIEF.md` 定为「唯一真相源」且要求每次开工必读，但它此前是 11 节全空的模板。

**为什么必须**：`AGENTS.md §9.2` 规定「发现任务书有漏洞 → 不要自行补全，提出疑问等确认」。本轮已确认两个事实：① 空模板会让「开工前必读」变成形式主义；② `AGENTS.md §8` 的 DoD 要求更新 `BOARD.md`，而 T-004 的 `outOfScope` 却排除 `docs/**`——两者不可能同时满足。

**要修的三件事**

1. 按 `SPEC.md` + 本计划书反推，补齐 `docs/TASK_BRIEF.md` 全部 8 节；每条验收标准必须可执行（数字 / 退出码 / 行数）
2. `§0.2` 增加 `$K`（治理脚本绝对路径），`§3` 步骤 6 改用它 —— 原文的 `push-task.mjs` 是相对路径，仓库内没有该脚本，照抄跑不通
3. `§0.2` 明确：`docs/BOARD.md` 是跨卡共享状态文件，**即使某卡把 `docs/**` 列为 outOfScope 也必须更新它**，否则违反 DoD

**验收命令**

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"

# 1) TASK_BRIEF 不得再留 HTML 占位符
Select-String -Path "$R\docs\TASK_BRIEF.md" -Pattern '<!--' | Measure-Object | Select-Object -ExpandProperty Count

# 2) 8 个章节齐全
Select-String -Path "$R\docs\TASK_BRIEF.md" -Pattern '^## \d' | ForEach-Object { $_.Line }

# 3) PLAN 里不得再出现相对路径的 push-task.mjs
Select-String -Path "$R\docs\PLAN.md" -Pattern 'push-task' | ForEach-Object { $_.Line.Trim() }

# 4) AGENTS §6 两条命令仍全绿
& $P -m compileall -q $R
& $P -m unittest discover -s "$R\tests" -t $R
```

**通过标准**
- 第 1 条输出 **0**（无 `<!--` 残留）
- 第 2 条列出 **8** 个 `## ` 章节
- 第 3 条每处 `push-task` 都带 `$K` 或绝对路径，**没有**裸 `push-task.mjs` 相对调用
- 第 4 条 `compileall` 退出码 0，单测 `OK`

**结论模板**

```
任务：T-011 补齐任务书与治理缺口
改动文件：docs/TASK_BRIEF.md、docs/PLAN.md、docs/BOARD.md
验收结果：
  [x] 占位符残留数 —— 实际：0
  [x] 章节数 —— 实际：8
  [x] push-task 路径 —— 实际：<粘贴>
  [x] compileall / 单测 —— 实际：exit 0 / Ran N tests, OK
遗留问题：<无 / 具体描述>
```

---

## T-012 · 排除 README 等说明文件被当作语料入库

| | |
|---|---|
| **难度 / 档位** | L1 / T1 |
| **依赖** | — |
| **inScope** | `src/ingest.py`、`tests/test_offline.py` |
| **outOfScope** | `SPEC.md`、`eval/**`、`data/raw/**`、`docs/**` |

**goal**：`read_raw_files` 不再把 `data/raw/README.md` 这类**说明文件**当作语料；`data/raw/` 的 12 份语料只产出 12 个来源。

**发现过程（由 T-007 核心卡暴露，非本卡）**：T-007 实测 `& $P -m src.ingest` 输出 **`files=13`**，而 `data/raw/` 的非 README 语料只有 **12** 份。

**最小复现（2026-09-18 实测，可直接粘贴）**

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Set-Location $R
$env:MOCK = "1"
& $P -m src.ingest     # 实际输出：files=13 chunks=405 mocked=True
& $P -c "import json,collections;rows=[json.loads(l) for l in open('data/chunks.jsonl',encoding='utf-8')];c=collections.Counter(r['source'] for r in rows);print('来源文件数 =',len(c));print('README.md 贡献块数 =',c.get('README.md',0))"
# 实际输出：来源文件数 = 13；README.md 贡献块数 = 5
```

**为什么是缺陷**：`data/raw/README.md` 是**语料格式说明书**（供人读），
`T-006` 的卡面验收也明确把它排除在语料计数之外（`Where-Object { $_.Name -ne 'README.md' }`）。
它被切块入库后，像「怎么放语料」这类**元信息**会参与检索、挤占 top-k，稀释真实文档的命中——属于检索噪声。

**修复方向（不限于此，实现者自主）**：在 `read_raw_files` 中跳过 `README.md`（不区分大小写），
并**补一条离线单测**锁住该行为（`AGENTS.md §6`：改行为必补测试）。

**验收命令**

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Set-Location $R
$env:MOCK = "1"
Remove-Item "$R\data\chunks.jsonl" -Force -ErrorAction SilentlyContinue
Remove-Item "$R\data\chroma" -Recurse -Force -ErrorAction SilentlyContinue
& $P -m src.ingest
& $P -c "import json,collections;rows=[json.loads(l) for l in open('data/chunks.jsonl',encoding='utf-8')];c=collections.Counter(r['source'] for r in rows);print('来源文件数 =',len(c));print('README 是否被入库 =', 'README.md' in c)"
& $P -m compileall -q $R
& $P -m unittest discover -s "$R\tests" -t $R
```

**通过标准**
- `files=12`（不再是 13），`chunks` > 0，`mocked=True`
- `来源文件数 = 12`、`README 是否被入库 = False`
- `compileall` 退出码 0；单测 `OK`，且**用例数比改动前多**（新增锁行为的用例）
- `data/raw/**` 一字未动（README 必须留在原处）

**红线**：不许靠「删掉 `data/raw/README.md`」让数字变绿 —— 那会同时违反 `T-006` 的通过标准（README 必须仍在）与 `AGENTS.md §7.1`。

**结论模板**

```
任务：T-012 排除 README 被入库
改动文件：src/ingest.py、tests/test_offline.py
验收结果：
  [x] ingest files=12 —— 原始输出：<粘贴>
  [x] README 是否被入库 = False —— 实际：<粘贴>
  [x] compileall / 单测 —— 实际：exit 0 / Ran N tests, OK（改动前 23）
遗留问题：<无 / 具体描述>
```

---

## T-013 · 让离线单测对环境变量隔离（MOCK 泄漏导致假失败）

| | |
|---|---|
| **难度 / 档位** | L1 / T1 |
| **依赖** | — |
| **inScope** | `tests/test_offline.py` |
| **outOfScope** | `SPEC.md`、`src/**`、`eval/**`、`docs/**` |

**goal**：无论调用者的 shell 里有没有导出 `MOCK`（以及其它 `load_settings` 会读的环境变量），`& $P -m unittest discover` 都必须给出**同样**的结果。

**发现过程（T-008 收尾时暴露）**：在同一个 shell 里先 `$env:MOCK='1'`（这正是 `README.md` 快速开始第 1 步教的命令），再跑 `AGENTS.md §6` 第二条命令 → `Ran 23 tests … FAILED (failures=1)`；把该变量清掉再跑 → `OK`。

**最小复现**

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Set-Location $R

$env:MOCK = '1'
& $P -m unittest discover -s "$R\tests" -t $R        # 实际：FAILED (failures=1)
Remove-Item Env:MOCK
& $P -m unittest discover -s "$R\tests" -t $R        # 实际：OK
```

失败点：`tests/test_offline.py:299`
`self.assertIs(config.load_settings(env_file=env_file).mock, expected, raw)`
→ `AssertionError: True is not False : 0`

**为什么是实现对、测试错**：`SPEC.md §5` 明确「环境变量优先级高于 `.env` 文件」。该用例往临时 `.env` 里写了 `MOCK=0` 并期望 `settings.mock is False`，但调用者 shell 里的 `MOCK=1` 按契约**本就该覆盖它** —— 所以 `load_settings` 的行为是正确的，**是用例没有隔离进程环境**。用户照 `README.md` 第 1 步导出了 `MOCK=1` 之后在同一 shell 跑测试，就会看到假失败。

**修复方向（实现者自主，但必须满足验收）**：让用例不依赖调用者的环境 —— 可用 `unittest.mock.patch.dict(os.environ, ...)` 在用例内（或 `setUp`/`tearDown`）把 `load_settings` 会读的键临时移除或固定。
**不得**放宽容宽（例如把 `assertIs` 改成 `assertIn`）、**不得** `skip` 用例、**不得**改 `src/config.py` 去迁就测试。

**验收命令**

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Set-Location $R

# 1) 泄漏环境下必须也全绿（当前实测 FAILED —— 这就是本卡要修的）
$env:MOCK = '1'
& $P -m unittest discover -s "$R\tests" -t $R -v
"leaked exit=$LASTEXITCODE"
Remove-Item Env:MOCK

# 2) 干净环境下仍全绿，且用例数不得减少
& $P -m unittest discover -s "$R\tests" -t $R -v
"clean exit=$LASTEXITCODE"

# 3) 再排一个同样会泄漏的键复测
$env:CHUNK_SIZE = '123'
& $P -m unittest discover -s "$R\tests" -t $R
"chunk exit=$LASTEXITCODE"
Remove-Item Env:CHUNK_SIZE

& $P -m compileall -q $R
```

**通过标准**
- 第 1 条：`OK`，退出码 0
- 第 2 条：`OK`，退出码 0，用例数 **≥ 改动前的 23**（不得靠删用例或 `skip` 变绿）
- 第 3 条：退出码 0
- 不得修改 `src/**` 与 `SPEC.md`

**结论模板**

```
任务：T-013 单测环境隔离
改动文件：tests/test_offline.py
验收结果：
  [x] MOCK=1 下全绿 —— 原始输出：<粘贴>
  [x] 干净环境下全绿且用例数 = N —— 原始输出：<粘贴>
  [x] CHUNK_SIZE=123 下全绿 —— 原始输出：<粘贴>
遗留问题：<无 / 具体描述>
```

---

## T-014 · `/chat` 的 `latency_ms` 应覆盖整个请求

| | |
|---|---|
| **难度 / 档位** | L1 / T1 |
| **依赖** | — |
| **inScope** | `app/main.py`（如需补测试，可加 `tests/test_offline.py`） |
| **outOfScope** | `SPEC.md`、`src/**`、`eval/**`、`docs/**` |

**goal**：`POST /chat` 返回的 `latency_ms` 反映**这次请求真正花了多久**（检索 + 生成），而不是只反映生成那一段。

**发现过程（T-010 交接收口轮，首次真正起服务时暴露）**

| 模式 | 接口报的 `latency_ms` | 客户端实测 |
|---|---|---|
| `MOCK=1` | **0** | 约 460 ms |
| `MOCK=0` | **1251** | **8217 ms** |

**根因**：`app/main.py` 优先返回 `answer.latency_ms`（生成段计时）；而 `Answer.latency_ms` 由 `Generator` / `MockGenerator` 各自测量，**都不包含检索**。
真实模式下检索含一次 query embedding 的 API 调用（约几百 ms）+ chroma 查询 + BM25（jieba 分词），mock 模式下检索仍是真跑，所以 **mock 反而把它暴露成 0**。

**最小复现**

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Set-Location $R
$env:MOCK = "1"
Start-Process -NoNewWindow $P -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000"
# 另开一个终端（连打两次，第二次避开冷启动）：
& $P -c "import json,time,urllib.request
for i in range(2):
    t0=time.perf_counter()
    req=urllib.request.Request('http://127.0.0.1:8000/chat',data=json.dumps({'question':'Vue 3 里 ref 怎么读值'}).encode(),headers={'Content-Type':'application/json'},method='POST')
    d=json.loads(urllib.request.urlopen(req,timeout=60).read())
    print('接口 latency_ms =',d['latency_ms'],' 客户端实测 =',round((time.perf_counter()-t0)*1000,1),'ms')"
# 实际输出：接口 latency_ms = 0   客户端实测 = ~460ms（两次都是）
```

**修复方向（实现者自主）**：在请求处理入口开始计时，覆盖检索 + 生成，直接返回该总耗时。
是否要把冷启动（首次构建 Retriever / BM25 索引）排除（例如启动时预热），由实现者判断，但**必须在代码注释里写明取舍**。

**验收命令**（mock 模式即可，免费；起服务后连打两次，取第二次避开冷启动）

```powershell
& $P -m compileall -q $R
& $P -m unittest discover -s "$R\tests" -t $R
```

**通过标准**
- mock 模式第二次 `POST /chat` 的接口 `latency_ms` **> 0**，且 **≥ 客户端实测 × 0.8**
- `compileall` 退出码 0；单测 `OK`，**用例数不得减少**（当前 25）
- 不得修改 `src/**` 与 `SPEC.md`；不得为了凑数字把接口延迟写死成常数

**结论模板**

```
任务：T-014 修正 /chat 延迟口径
改动文件：app/main.py（+ 测试，若有）
验收结果：
  [x] mock 第二次请求：接口 latency_ms = ?，客户端实测 = ?，比值 = ? —— 原始输出：<粘贴>
  [x] compileall / 单测 —— 实际：exit 0 / Ran N tests, OK
遗留问题：<冷启动是否已处理 / 无>
```

---

## 3. 单卡执行循环

```
1. 领卡    → 从 docs/BOARD.md 认领，一次只领一张
2. 读约束  → 重读 AGENTS.md §6/§7 + 本卡验收命令
3. 开分支  → & "C:\Program Files\Git\cmd\git.exe" switch -c feat/T-0xx-描述
4. 做      → 小步改，每步可运行
5. 验      → 逐条跑本卡验收命令，记**原始输出**（不许口头声称）
6. 交      → & "C:\Program Files\nodejs\node.exe" $K "$R" -m "feat(T-0xx): 描述"
7. 收      → 更新 docs/BOARD.md
```

任一步失败超过 2 次 → 停止，写 `docs/BOARD.md` 阻塞区，说明已尝试过什么。

## 4. 状态定义

| 状态 | 含义 |
|---|---|
| 待办 | 还没开始 |
| 进行中 | 已被认领（同时只允许一个） |
| 待审 | 自测通过，等待复核 |
| 完成 | 验收命令逐条通过，且已合并推送到远端 |
| 阻塞 | 卡住，必须写明原因与已尝试的方案 |

## 5. 本计划的已知限制

1. **T-006 / T-009 需要用户参与**：语料要用户提供，API key 要用户填。Agent 不能也不该编造。
2. **`MOCK` 模式仍需要 `chromadb`**（`SPEC.md §5` 明确）—— 所以 T-004 是 T-007 的硬前置。
3. **真实评测会产生 API 费用**（Embedding + 生成），T-009 执行前需用户确认。
4. **本计划的验收数字均为"当轮实测"**：语料/题库一变，数字就变，不可跨轮直接比较。
5. **真实评测的数字有运行间波动**：同输入、`temperature=0` 连跑，`accuracy` 实测落在 **0.45–0.50**（旧语料 0.45 / 0.50，最终语料 0.45）；`partial_rate` 在 **0.30–0.35**、`wrong_rate` 在 **0.20–0.25** 之间同步移动；而 `refusal_accuracy` / `hit_rate` 三次运行**全部稳定在 1.00 / 0.80**。
   原因是 `correct` 与 `partial` 的边界取决于模型输出措辞（`keypoints` 覆盖率是否 ≥ 0.8），模型即使温度为 0 也不是逐字确定的。
   **引用时必须注明"单次运行"，或写成区间（如 accuracy 45%–50%）**；不要把波动误读成"改了东西导致退化"。
6. **`multi_hop` 是当前最弱项**：最终语料上分类实测 `multi_hop` accuracy **0.20**（5 题：1 完全对 / 3 部分对 / 1 错，**检索命中 5/5**）、`single_hop` **0.42**（12 题：5/3/4，检索命中 11/12）、`unanswerable` **1.00**（3 题全部正确拒答）。
   疑似原因：多跳题需要跨两篇文档综合，而检索是 `top_k_final=4` 的单块拼接，跨文档的另一半依据容易被挤掉；且多跳题的 `keypoints` 更多，更容易落在"部分对"。**属现状而非缺陷**；多路召回 / 父子分块 / query 改写属 `SPEC.md` 非目标清单，留二期。
7. **`data/raw/README.md` 的噪声曾被实测确认，现已由 T-012 修复**：T-009 首次评测时（该文件仍入库），3 道拒答题虽全部正确拒答，但模型回答里出现了「资料里提到了……数据库设计……的文档」—— 它读到了 `README.md` 里那份"建议语料清单"的**文件名**。T-012 已把说明文件排除出语料（`files` 13 → 12，`chunks` 405 → 400）。
8. **生成侧存在偶发"过度保守"**：`q12`（可答题，检索 `hit=True`）在两次运行中一次被答成「根据现有资料无法回答」、一次正常作答。属生成行为而非检索缺陷，且本身也是运行间波动的一部分，记录备查、暂不开卡。
9. **T-012 去掉噪声的效果在 20 题分辨率下测不出来**（对照实验）：同一套题分别在「含 README（13 份 / 405 块）」与「不含（12 份 / 400 块）」两种语料上各跑一次 ——
   `accuracy` **0.45 → 0.45**、`hit_rate` **0.80 → 0.80** 完全不变；仅 `partial_rate 0.35 → 0.30`、`wrong_rate 0.20 → 0.25`（一题从"部分对"落到"错"），幅度落在 §5.5 的波动范围内。
   **结论：T-012 的价值在于索引干净与语义正确，而不是分数提升**；做这个对照的意义正是**避免把噪声当成"分数变好了"**。
10. **`/chat` 的 `latency_ms` 口径已修正（T-014，2026-09-18 完成）**：原实现优先采用 `Answer.latency_ms`（只含生成段），导致 mock 模式报 **0 ms**（客户端实测约 460 ms）、真实模式报 **1251 ms**（客户端实测 **8217 ms**）。
    现改为**请求作用域计时**（lazy 构建 + 检索 + 生成），captain 双模式复测：mock **452 / 466.8 ms（比值 0.97）**、真实 **1700 / 1705.4 ms（比值 1.00）**。
    冷启动**计入**（首次 mock 3891 ms、真实 10516 ms），取舍理由见 BOARD 决策日志。
    评测报告里的 `avg_latency_ms` 由 `eval/run_eval.py` 独立计时（覆盖检索 + 生成），自始不受此缺陷影响。
11. **「环境变量优先于 `.env`」这条契约没有落盘测试**：`tests/test_offline.py` 未覆盖 `SPEC.md §5` 的这条优先级规则（T-004 时只有临时断言验过，未提交）。属既有覆盖缺口、非 T-013 引入；如需补测请另开卡，不要顺手改 T-013 的卡面。

## 6. 变更记录

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-09-18 | 初版（把模板示例换成真实卡） | 模板里的 T-001~T-003 是示例，与 `SPEC.md` 无关；实际代码已实现，缺口在依赖/题库/集成验收 |
| 2026-09-18 | 把 `MOCK=1` 全链路验收定为**核心卡 T-007** | 这是唯一不需要 API key 就能证明项目可跑的路径；先证明能跑，再花钱 |
| 2026-09-18 | 新增 T-011（治理链修复），并把 `$K` 写进 §0.2 | 用户确认：`TASK_BRIEF.md` 空模板必须补；实测 `push-task.mjs` 相对路径跑不通；DoD 与 T-004 的 outOfScope 直接冲突 |
| 2026-09-18 | 新增 T-012（README 被当语料入库的缺陷修复） | T-007 核心卡实测 `files=13` 而非 12：`data/raw/README.md` 被切块入库，会让「怎么放语料」这类元信息参与检索、稀释真实文档命中 |
| 2026-09-18 | 新增 T-013（离线单测未隔离环境变量） | T-008 收尾时在 `MOCK=1` 的 shell 里跑 AGENTS §6 第二条命令得到 `FAILED (failures=1)`，未设该变量时 `OK`；`SPEC.md §5` 规定环境变量优先于 `.env`，**实现是对的、用例没隔离环境**。而 `README.md` 第 1 步恰好教用户 `$env:MOCK = "1"`，照做再跑测试就会看到假失败 |
| 2026-09-18 | T-009 产出首个真实数字；把「运行间波动」「multi_hop 最弱」「README 噪声被引用」「生成侧过度保守」四条写进 §5 已知限制 | 同参数连跑两次 `accuracy` 0.45 vs 0.50 —— 不写清楚，后续会把正常波动当成"改坏了"；分类数据显示多跳题是短板，必须在报告与简历里如实标注，而不是只报 0.45 这个好看的总数 |
| 2026-09-18 | T-012 / T-013 关闭；新增 T-014（`/chat` 延迟口径） | T-012 去掉了入库噪声（13→12 份），T-013 消除了 `MOCK` 泄漏导致的单测假失败；T-014 是 T-010 首次真正起服务时暴露的：接口报的 `latency_ms` 不含检索（mock 下报 0、真实下报 1251 而客户端实测 8217） |
| 2026-09-18 | T-009 的数字按**最终语料**刷新一次，并把「去噪声前后对照」结论写进 §5.9 | 语料从 13 份 405 块变成 12 份 400 块，原数字对应一个已不存在的语料状态；对照结果显示 `accuracy`/`hit_rate` 未变，只有落在波动范围内的一题差异 —— 如实记录「测不出来」，避免把噪声当成分数提升 |
| 2026-09-18 | T-014 修掉 `/chat` 的 `latency_ms` 口径；**全项目 14 / 14 闭环** | 该字段只覆盖生成段：mock 报 0 / 客户端 460 ms、真实报 1251 / 客户端 8217 ms，「接口延迟」名不符实；改为请求作用域计时后，比值从 **0.15 回到 1.00** |
