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
| T-008 | 按真实语料出 20 题正式题库 | T-006 | T1 | 待办 |
| T-009 | 真实模式 20 题评测，产出报告 | T-007, T-008 | T1 | 待办 |
| T-010 | 文档与交接收口 | T-009 | T2 | 待办 |

## 2.5 里程碑 M3 · 治理链修复（可与其他卡并行）

| ID | 任务 | 依赖 | 档位 | 状态 |
|---|---|---|---|---|
| T-011 | 补齐 TASK_BRIEF 并修掉治理矛盾 | — | L1 / T1 | **完成** |

## 2.6 里程碑 M4 · 缺陷修复（可与其他卡并行）

| ID | 任务 | 依赖 | 档位 | 状态 |
|---|---|---|---|---|
| T-012 | 排除 README 等说明文件被当作语料入库 | — | L1 / T1 | 待办 |

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

## 6. 变更记录

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-09-18 | 初版（把模板示例换成真实卡） | 模板里的 T-001~T-003 是示例，与 `SPEC.md` 无关；实际代码已实现，缺口在依赖/题库/集成验收 |
| 2026-09-18 | 把 `MOCK=1` 全链路验收定为**核心卡 T-007** | 这是唯一不需要 API key 就能证明项目可跑的路径；先证明能跑，再花钱 |
| 2026-09-18 | 新增 T-011（治理链修复），并把 `$K` 写进 §0.2 | 用户确认：`TASK_BRIEF.md` 空模板必须补；实测 `push-task.mjs` 相对路径跑不通；DoD 与 T-004 的 outOfScope 直接冲突 |
| 2026-09-18 | 新增 T-012（README 被当语料入库的缺陷修复） | T-007 核心卡实测 `files=13` 而非 12：`data/raw/README.md` 被切块入库，会让「怎么放语料」这类元信息参与检索、稀释真实文档命中 |
