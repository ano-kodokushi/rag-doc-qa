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
$K = "C:\Users\a2695\Desktop\作业\Agent\agent-project-kit\push-task.mjs"   # 治理脚本：在工作区根目录，**不在仓库内**，禁止用相对路径
# ⚠️ 这是**仓库外的本机路径**，会随工作区整理而失效（T-017 就是因为它被移动才发现）。
#    若报「Cannot find module」→ 先定位再改这里：
#      Get-ChildItem "C:\Users\a2695\Desktop\作业\Agent" -Recurse -Filter push-task.mjs
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
| T-017 | 修正治理脚本路径（`$K` 已失效） | — | L0 / T2 | **完成** |

## 2.6 里程碑 M4 · 缺陷修复（可与其他卡并行）

| ID | 任务 | 依赖 | 档位 | 状态 |
|---|---|---|---|---|
| T-012 | 排除 README 等说明文件被当作语料入库 | — | L1 / T1 | **完成** |
| T-013 | 让离线单测对环境变量隔离（MOCK 泄漏导致假失败） | — | L1 / T1 | **完成** |
| T-014 | `/chat` 的 `latency_ms` 只覆盖生成段，不含检索与冷启动 | — | L1 / T1 | **完成** |

> **M4 全部闭环**：T-012 / T-013 / T-014 均已修复并推送。**全项目 14 / 14 卡片完成，零待办。**

## 2.7 里程碑 M5 · 性能优化

| ID | 任务 | 依赖 | 档位 | 状态 |
|---|---|---|---|---|
| T-015 | 缓存检索索引，消除每次查询重建 BM25 的开销 | — | L1 / T1 | **完成** |

> **M5 闭环**：单次检索 **401.6 ms → 10.7 ms（-97.3%）**，真实评测端到端 **1654.6 ms → 1316.3 ms（-20.4%）**；同进程 A/B 证明结果**逐字中性**（差异 0 处）。

## 2.8 里程碑 M6 · 检索侧对照实验

| ID | 任务 | 依赖 | 档位 | 状态 |
|---|---|---|---|---|
| T-016 | multi-hop 检索侧改进的对照实验 | — | L1 / T1 | **完成**（结论已被 E-02 修正） |
| T-018 | 修正 E-01 的错误结论，记录「指标粒度」教训 | — | L1 / T1 | **完成** |

> ⚠️ **M6 的结论已修正（T-018 / E-02）**：E-01 原判「`multi_hop` 一分未动 → 检索侧无效、瓶颈在生成侧」**是错的**。
> 用**连续 keypoint 覆盖率**重读同一批数据：V1(top-4) → V2(top-8) **上升 5 题 / 下降 0 题**（多跳均值 **0.450 → 0.550**，**p ≈ 0.031**）——
> 扩大召回**有真实效果，只是没跨过 0.8 的桶阈值，于是桶看不见**。
> 真正的瓶颈是**小节级检索精度**（检索到同一文件的错误小节），既不是文件级召回，也不是生成侧。
> 详见 `docs/EXPERIMENTS.md` 的 **E-02**（E-01 原文保留以便对照，第 5 节已标注被推翻）。

**DAG**

```
T-004 ─┬─→ T-005 ─┐
       │          ├─→ T-007 ─→ T-009 ─→ T-010
T-006 ─┴──────────┘        ↗
       └─→ T-008 ──────────
```

## 2.9 里程碑 M7 · 指标改造（先修仪器）

| ID | 任务 | 依赖 | 档位 | 状态 |
|---|---|---|---|---|
| T-019 | 把「连续 keypoint 覆盖率」接进评测报告 | — | L1 / T1 | **完成**（2026-09-21） |

> **为什么先做这张卡**：E-02 的教训是「**粒度决定了你能看见什么**」——
> 桶指标把「覆盖率 0.450 → 0.550、逐题 5 升 0 降」压成了"一分未动"。
> 补救办法不是每次写临时脚本回读逐题明细，而是让**报告天生带连续覆盖率**；
> 否则 T-020（小节级上下文）做完了照样测不出效果。
> 契约影响（对 SPEC 汇总字段清单的**向后兼容扩展**）登记在 **§5.13**。

## 2.10 里程碑 M8 · 小节级上下文对照（**假设被证伪**）

| ID | 任务 | 依赖 | 档位 | 状态 |
|---|---|---|---|---|
| T-020 | 小节级整理三模式对照（`off` / `diverse` / `expand`） | T-019 | L1 / T1 | **完成**（默认保持 `off`） |

> ⚠️ **M8 是负结果**：E-02 把瓶颈定位到「检索到同一文件的**错误小节**」，于是假设「按小节整理上下文能救」。
> 三次真实评测（唯一自变量 `SECTION_MODE`）**没有支持这个假设**：
> `diverse` 覆盖率 **0.5343 → 0.5147（更差）**；`expand` **0.5441（+0.010，噪声内）**，却让 **14/20 题丢资料**（4 题连第 1 条都塞不下）、`q04` 从 1.00 掉到 0.00。
> → **默认保持 `off`**，代码作为可复现实验装置保留。详见 `docs/EXPERIMENTS.md` **E-03**。
>
> **三个实验合起来的结论**：`top_k` 4→8（**内容更多**）→ 5 升 0 降 ✅；`diverse`（**内容更少**）→ 更差；`expand`（**更长但被截断**）→ 持平偏险。
> **真正决定成败的是「上下文里有没有那段内容」，而不是怎么排列它**。
>
> **矛头指向（未开卡）**：需要的内容**已经在融合池里**（E-01 证：文件级 5/5），只是没进 top-k 窗口 ——
> 这是**排序**问题，正是 `RERANK_ENABLED=0` 那条**已实现但从未启用、也从未联网验证**的可选路径该解决的。
> → **已开卡：T-021（M9）**。

## 2.11 里程碑 M9 · 把 rerank 从「写了但没跑过」变成「跑过且有数字」

| ID | 任务 | 依赖 | 档位 | 状态 |
|---|---|---|---|---|
| T-021 | 启用并真实验证 rerank（契约核对 → 连通性 → 对齐 → A/B → 降级验证） | — | L1 / T1 | **完成**（**有效**；默认值仍为 `0`） |

> **为什么是这张卡**：E-01 / E-02 / E-03 三个实验把矛头收敛到**排序**（需要的内容在融合池里、却没进 top-k 窗口）。
> 而 `src/retrieve.py:203-288` 的 rerank **一期实现了、默认关闭、从未联网验证过** ——
> 它现在是唯一一条「有证据支持、但还没有数字」的路。
>
> **Step 0 已在开卡时做完（0 元，联网核对官方契约）**，结论有一处**重要且必须处理**的差异：
> 1. ✅ **请求/响应字段与我们实现一致**（`gte-rerank-v2` 用 `input.{query,documents}` + `parameters.top_n`，返回 `output.results[].{index,relevance_score}`）
> 2. ⚠️ **官方已公告 `gte-rerank` 下线、推荐 `qwen3-rerank`**（文档更新于 2026-09-04）——而 `qwen3-rerank` 是**另一套形状**：请求扁平（无 `input`/`parameters` 包裹）、**响应 `results` 直接在顶层**、且端点是 `/compatible-api/v1/reranks`
> 3. ⚠️ **我们配的是老的全局端点** `dashscope.aliyuncs.com/api/v1/...`，而文档现在给的是**业务空间域名** `{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/...`
>
> → 所以 T-021 **不是"打开开关测一下"**：先得确认老端点/老模型是否还能用，再决定是"沿用 gte"还是"补一条 qwen3-rerank 分支"。
>
> **红线**：`RERANK_ENABLED` 的默认值**保持 `0`**。本卡只产出证据与实现，改默认值要另开卡 + 用户批准。

> ✅ **结项补充（2026-09-21，已执行完）** —— **M9 是本项目第一个正面结果**，但它**不是这条证据链的收口**：
> **内容在池子里（E-01）→ 扩大窗口对多跳有效（E-02）→ 排列方式无效（E-03）→ 排序对单跳有效、对多跳无效（E-04）**。
>
> **实测（同进程 A/B，唯一自变量 `use_rerank`，见 `EXPERIMENTS.md` E-04）**：
> 主指标 `avg_keypoint_coverage` **0.5490 → 0.6373（+0.088）**、`wrong_rate` **0.20 → 0.10**、`hit_rate` 0.80 → 0.85、逐题 **升 4 / 降 1**；
> 代价是单题延迟 **1136 → 3188 ms（+2.05 s）**。
> 三条"确实生效"的证据：`_rerank` 被调 **20 次 0 异常**、**20/20 题 top-k 顺序被改变**、输出**全部来自融合池（0 违反）**。
>
> ⚠️ **但按题型拆开后目标没达成（本卡最重要的一条）**：`single_hop` 覆盖率 **0.5694 → 0.6944（+0.125）**（桶内 5/4/3 → 6/5/1）；
> **`multi_hop` 覆盖率 0.5000 → 0.5000（±0.000）**、桶内 **1/3/1 → 1/3/1 完全没变**（`q16` +0.25 被 `q14` −0.25 精确抵消）。
> **收益全部来自单跳题 —— 而本卡的动机是多跳。** ⇒ 排序是全库的瓶颈之一，但**不是多跳的瓶颈**；
> 多跳的瓶颈仍未找到（已排除：文件级召回、窗口大小（部分）、材料排列、全局重排）。
> 最值得先测的下一个假设见 `§5.15` 末条：**`top_k` 扩大 + rerank 联合**（让 rerank 只排序、不替多跳题做取舍）。
>
> **Step 1 把开卡时的问号都回答了，而且答案比文档更宽松**：
> - 老全局端点 + `gte-rerank-v2` → **HTTP 200**，响应形状与实现一致 ⇒ **走 A 路径，`src/retrieve.py` 零改动**
> - 老全局端点 + `qwen3-rerank` + **同一套嵌套 body** → **HTTP 200** ⇒ 官方推荐的替代模型**可纯靠 `RERANK_MODEL` 切换**
>   （**但这是实测行为、不是文档承诺** —— 文档说的是扁平形状；要连同"静默降级"的陷阱一起记，见 `§5.15`）
> - 文档里的 `/compatible-api/v1/reranks`（及其 `compatible-mode` 变体）在老域名上 → **404** ⇒ **不能**按文档把 `_rerank` 改成扁平形状，那会把能用的实现改坏
>
> **默认值仍为 `0`**（红线已兑现）：收益偏质量、成本偏延迟（+1.8 倍），该由使用方按场景权衡；在线启用属于另一张卡。

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

## T-015 · 缓存检索索引，消除每次查询重建 BM25 的开销

| | |
|---|---|
| **难度 / 档位** | L1 / T1 |
| **依赖** | — |
| **inScope** | `src/retrieve.py` |
| **outOfScope** | `SPEC.md`、`eval/**`、`app/**`、`src/` 的其它文件 |

**goal**：同一进程内连续检索不再重复构建 BM25 索引与 chunk 映射；**检索结果逐字不变**，只变快。

**发现过程（T-014 收口后核事实时被量化）**

`search()` 每次调用 `_rankings()`，而它内部是 `KeywordIndex.from_chunks_file(...)` —— **每检索一次就把整份 `chunks.jsonl` 重读一遍、重建一次 BM25 索引**（`src/retrieve.py:45,144`）；紧接着 `_chunk_map()` 又读一遍全量（`:145`）。
实测（400 块，mock 模式，5 次平均）：

| 环节 | 耗时 |
|---|---|
| 重建一次 BM25 索引 | **432.9 ms** |
| 读全量建 id → Chunk 映射 | 8.4 ms |
| 一次完整 `search` | 445.6 ms |
| **两者合计占检索耗时** | **99.0%** |

即：真正的向量查询 + BM25 打分只有约 **13 ms**。端到端 1654.6 ms ≈ 生成约 1.2 s + 检索 0.44 s，而检索那 0.44 s 里几乎全是**白建索引**。

**修复方向（实现者自主，但必须满足验收）**
把 `KeywordIndex` 与 chunk 映射**缓存在 `Retriever` 实例上**：首次使用时构建、之后复用。
失效点现成 —— `app/main.py:123` 在 `/ingest` 之后已经调用 `get_retriever.cache_clear()`（`lru_cache`），整个 Retriever 会被丢弃重建，所以实例级缓存是安全的。建议再提供一个显式的实例方法（如 `clear_cache()`）供调用方主动失效，并在 docstring 里写明「进程内缓存、语料变更必须失效」。

**红线**：**不得改变任何可观测的检索结果** —— `vector` / `bm25` / `fused` / `final` 的 id 顺序与分数、以及 `Hit` 的 `source` / `retriever` 字段都必须与改动前**逐字一致**。缓存改动只允许变快。

**验收命令**

```powershell
$P = "C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe"
$R = "C:\Users\a2695\Desktop\作业\Agent\rag-doc-qa"
Set-Location $R
$env:MOCK = "1"

# 1) 结果中性：**同进程内** A/B —— 缓存路径 vs 强制每次重建路径，逐字比对
#    （不能用"跨进程黄金基线 diff"，理由见 §验收标准的修正）
& $P "$env:TEMP\t015_ab.py"         # 本卡执行者编写；输出"差异 = N 处"与 0 差异判定

# 2) 延迟下降：同样 5 次平均
& $P "$env:TEMP\t015_bench.py"

Remove-Item Env:MOCK
& $P -m compileall -q $R
& $P -m unittest discover -s "$R\tests" -t $R
```

**通过标准**
- 第 1 条：**同进程内**，缓存路径与「强制每次重建」路径在 **20 题的 `vector` / `bm25` / `fused` / `final` / `hits` 上逐字一致（差异 = 0 处）**
- 第 2 条：一次完整 `search` 耗时**下降 ≥ 80%**（445.6 ms → 预期 15 ms 量级）
- `compileall` 退出码 0；单测 `OK`，用例数不得减少（当前 **25**）
- `& "C:\Program Files\Git\cmd\git.exe" -C $R status --short` 只出现 ` M src/retrieve.py`
- 不得改动 `data/**`、`eval/**`、`app/**`、`SPEC.md`

**关于单测**：本卡**不改变可观测行为**（这是硬性要求），所以用「同进程 A/B 逐字 diff」作为回归证据，而不是硬凑单测 —— `Retriever` 依赖 `chromadb`，无法在纯标准库的 `tests/test_offline.py` 里实例化（`AGENTS.md §6`）。
若实现者能设计出**不引入第三方依赖**的缓存语义测试（例如把缓存取数抽成可离线测试的纯函数），欢迎补上并计入用例数。

---

### 验收标准的修正（2026-09-18，**重要，不是放宽标准**）

本卡初版写的第 1 条是「重跑 20 题检索，与改动前抓的**跨进程**黄金基线逐字 diff 为空」。**这条标准经实测证明天生不可达**，任何实现（包括未改动的原版代码）都过不了：

| 被测对象 | 与黄金基线的差异层数 |
|---|---|
| 带缓存的新代码 | 6 / 6 / 2（三次运行） |
| **未改动的原版代码** | **10 / 6**（两次运行） |

差异全部落在 `vector` / `fused` / `final` / `hits`，**`bm25` 从不出现**（说明 `chunks.jsonl` 没变）。也就是说：**chroma 向量层的输出会随索引状态与 ANNS 内部行为漂移**，与本次缓存改动无关。

因此第 1 条改为**同进程内 A/B**：两条路径共享同一个 chroma 状态，差异只可能来自缓存本身 —— 这才是本卡真正要保证的性质。这个替换**在相关维度上更严格**（20 题 × 5 个层全部逐字比对，且排除了所有外部噪声），而不是更宽松。

> 派生发现（已记入 §5 已知限制 12）：**向量检索层的结果不可跨进程复现** —— 这会影响任何依赖检索的指标（如 `hit_rate`）的严格可复现性。实测中 `hit_rate` 三次都稳定在 0.80，但这是"指标层稳定"，不等于"每次召回的 chunk 排名一致"。

**结论模板**

```
任务：T-015 缓存检索索引
改动文件：src/retrieve.py
验收结果：
  [x] 同进程 A/B 逐字 diff —— 实际：差异 0 处
  [x] 一次 search 耗时 —— 445.6 ms → ??? ms（下降 ??%）
  [x] compileall / 单测 —— 实际：exit 0 / Ran N tests, OK
遗留问题：<语料变更时的失效路径是否已说明 / 无>

```

---

## T-016 · multi-hop 检索侧改进的对照实验

| | |
|---|---|
| **难度 / 档位** | L1 / T1 |
| **依赖** | — |
| **inScope** | `docs/EXPERIMENTS.md`（新建：实验设计与原始数据）、`docs/PLAN.md`、`docs/BOARD.md`、`eval/report*.json`（产物） |
| **outOfScope** | `SPEC.md`、`eval/questions.jsonl`（**题库已定稿，一字不许改**）、`data/**`、`src/**`、`app/**` |

**goal**：用**受控对照**回答一个问题 —— 把检索侧的候选范围改一改，`multi_hop` 到底动不动？

**为什么需要这张卡**：`multi_hop` 是最弱的一类（accuracy 0.20，5 题里只有 1 题完全正确），而项目目前**缺一个「前后对比」的数字**。这张卡就是去补它 —— 但必须做成真正的对照，而不是"改完就报变好了"。

**方法论前提（本卡最重要的部分，写在最前面）**

1. **只有 5 道多跳题** → 1 题翻转就是 0.20 → 0.40。**这个样本量做不了统计推断**，任何"提升"都只能当**方向性证据**，报告里必须写明。
2. 因此**主指标不用准确率**，改用检索层的可诊断指标：`gold_sources` 里的**全部**依据是否都进了候选池 / top-k。
   原因：`eval/metrics.py` 的 `hit_at_k` 是「**任一** gold_source 命中即算命中」，所以现在 `multi_hop` 报的 `hit 5/5` **只说明两篇依据里找到了至少一篇**，并不代表两篇都进了 top-4 —— 这很可能就是失分处，而现有指标看不出来。
3. **受控条件**：题库冻结、语料冻结、模型冻结，**只改检索**。

**Step 0 · 诊断（几分钱：只调 query embedding，不调生成）**
对 5 道 `multi_hop` 题分别统计：
- 两篇 `gold_sources` 里有几篇进了**融合池**（`fused`）
- 有几篇进了**最终 top-4**（`final`）
- 该题判分（correct / partial / wrong）与上面两栏的对应关系

**决策点（必须显式记录走了哪条）**
- 若 top-4 里**经常只有 1 篇** → 检索是瓶颈 → 进 Step 1
- 若**两篇基本都进了** → **停止**，本卡以**负结果**收尾：结论为「瓶颈在生成侧（跨文档综合），不在检索」，并写进文档。
  **负结果也是合格交付**，不许为了"有提升"而硬改。
  > ⚠️ **这条结论后来被 E-02 推翻**（同一批数据换连续覆盖率后是「逐题 5 升 0 降」）。
  > 保留原文是为了留下「同一个实验在两种指标粒度下给出相反结论」的证据；**引用时以 `§5.6` / E-02 为准**。

**Step 1 · 变体对照（每个变体约 0.1 元）**
在**同一套 20 题、同一份语料、同一模型**上，只改检索（`TOP_K_FINAL` 是环境变量，改它**不需要动代码**）：
- V1 基线：`TOP_K_FINAL=4`（已有数字：accuracy 0.50 / multi_hop 0.20 / hit_rate 0.80）
- V2：`TOP_K_FINAL=8`
- V3（可选，需在卡里先说明理由）：按来源限流（保证 top-k 跨文档覆盖）或父子分块

每个变体产出：总体 + **分题型**的 correct/partial/wrong + **「两篇依据都进 top-k」的比例** + `avg_latency_ms`。

**通过标准**
- `docs/EXPERIMENTS.md` 里有**对照表**（V1 / V2 / [V3] × 各指标），并附**原始命令与原始输出**
- 写明**方法学限制**：5 题样本量、准确率的运行间波动（§5.5，0.45–0.50）、主指标为何改用检索层可诊断指标
- 结论句必须区分「方向性证据」与「统计显著」
- **题库与语料一字未改**（`git status` 不出现 `eval/questions.jsonl` 与 `data/**`）
- 若结论是"某变体更好"，**不要在本卡里直接改默认值** —— `SPEC.md §5` 定义了 `TOP_K_FINAL=4`，改默认值需先改契约（**另开卡 + 用户批准**）
- 成本 **≤ 0.5 元**

**结论模板**

```
任务：T-016 multi-hop 检索侧对照实验
走了哪条路径：<Step 1 变体对照 / 负结果收尾>
Step 0 诊断 —— 原始输出：<粘贴 5 题的两栏命中情况>
对照表 —— V1: ... / V2: ...（含分题型与“两篇都进”比例）
方法学限制 —— 5 题样本量、波动区间、主指标选择理由
结论 —— 方向性：<…>；统计显著：<否，样本量不足>
遗留问题：<若要改默认值，需改 SPEC 的另一张卡>
```

---

## T-017 · 修正治理脚本路径（`$K` 已失效）

| | |
|---|---|
| **难度 / 档位** | L0 / T2 |
| **依赖** | — |
| **inScope** | `docs/PLAN.md`、`docs/BOARD.md` |
| **outOfScope** | `AGENTS.md`、`SPEC.md`、`src/**`、`eval/**`、`data/**` |

**问题**：`§0.2` 里 `$K = "...\_kit_inspect\agent-project-kit\push-task.mjs"` **已指向不存在的路径** —— 工作区整理时 `agent-project-kit/` 被移到了**工作区根目录**。
后果：下一个会话照 `§3` 步骤 6 抄命令会直接 `MODULE_NOT_FOUND`，**推不上去**（T-016 提交时就撞上了，临时改用新路径才推成功）。

**修复**：把 `$K` 更新为新位置，并补一条「先确认存在 / 找不到时怎么定位」的提示。
后者比前者更重要 —— `$K` 是**仓库外的本机路径**，会随工作区整理反复失效；写死一次不等于以后都对。

**验收（自证型：本卡的提交本身就是验收证据）**

```powershell
# 1) 路径存在
Test-Path "C:\Users\a2695\Desktop\作业\Agent\agent-project-kit\push-task.mjs"

# 2) 用 §3 步骤 6 的命令真的跑一次闭环
#    —— 若 $K 写错，这条会以 MODULE_NOT_FOUND 失败；成功即证明修复有效
& "C:\Program Files\nodejs\node.exe" $K "$R" -m "chore(governance): 修正治理脚本路径 $K（T-017）"
```

**通过标准**
- 第 1 条为 `True`
- 第 2 条真的完成「提交 → 推分支 → **快进合并 main** → 推 main」
- `AGENTS.md` **不需要改**：已用 `grep` 确认它**零命中** `push-task`（它从不引用这个脚本）
- `SPEC.md`、`src/**`、`eval/**`、`data/**` 一字未动

**结论模板**

```
任务：T-017 修正治理脚本路径
改动文件：docs/PLAN.md、docs/BOARD.md
验收结果：
  [x] Test-Path $K —— 实际：True
  [x] 用 $K 跑通闭环 —— 实际：<提交 hash + 已推送 main>
  [x] grep 确认 AGENTS.md 无需改 —— 实际：push-task 命中 0
遗留问题：<路径仍可能再变；已在 §0.2 写明如何定位>
```

---

## T-018 · 修正 E-01 的错误结论，记录「指标粒度」教训

| | |
|---|---|
| **难度 / 档位** | L1 / T1 |
| **依赖** | — |
| **inScope** | `docs/EXPERIMENTS.md`、`docs/PLAN.md`、`docs/BOARD.md` |
| **outOfScope** | `SPEC.md`、`src/**`、`eval/**`、`data/**` |

**目标**：仓库里现在存着一条**已被证伪的结论**（E-01：「检索侧无效、瓶颈在生成侧」），而 `PLAN.md §2.6/§5.6` 都引用了它。
不修就会一路错到面试里。

**为什么是"重读"而不是"重做"**：E-01 的**原始数据是好的**（`eval/report*.json` 都在），错的是**指标口径**。
用 `keypoints_match` 的**连续值**重读同一批数据 → 覆盖率 **5 升 0 降**（**p ≈ 0.031**）。**本卡不花任何 API 费用**，是纯分析。

**验收**
- `docs/EXPERIMENTS.md` 新增 **E-02**：重读结果表、三层指标对照、逐题证据、方法学教训、对后续实验的约束
- `E-01` 第 5 节顶部加「**已被 E-02 推翻**」的显式标注，**原文保留**（不删历史，便于对照）
- `PLAN.md §2.6` 的 M6 结论与 `§5.6` 一并修正；顺带修掉 §5 里**重复的编号 7**
- `git status` 不出现 `eval/**`、`data/**`（纯文档修正，不动代码与数据）

**成本**：**0 元**（只用已有数据）

**结论模板**

```
任务：T-018 修正 E-01 结论
改动文件：docs/EXPERIMENTS.md、docs/PLAN.md、docs/BOARD.md
验收结果：
  [x] E-02 已写入（含 5 升 0 降与 p≈0.031）—— 实际：<粘贴关键行>
  [x] E-01 已标注被推翻且原文保留 —— 是
  [x] §2.6 / §5.6 已修正，§5 重复编号已清零 —— 是
  [x] 未动 eval/** 与 data/** —— git status 仅 docs/**
遗留问题：工作区里的 RAG项目_面试问答.md（不在仓库）有同类表述，需另行同步
```

---

## T-019 · 把「连续 keypoint 覆盖率」接进评测报告

| | |
|---|---|
| **难度 / 档位** | L1 / T1 |
| **依赖** | — |
| **inScope** | `eval/metrics.py`、`eval/run_eval.py`、`tests/test_offline.py`、`docs/**` |
| **outOfScope** | `SPEC.md`、`src/**`、`app/**`、`data/**`、`eval/questions.jsonl` |

**目标**：让评测报告**天生带连续覆盖率**，不再靠临时脚本回读逐题明细（E-02 的「先修仪器，再改系统」）。

**验收**
- `run_once` 的逐题记录新增键 `keypoint_coverage`（= `keypoints_match(pred, keypoints)` 的连续值）
- `aggregate` 新增 `avg_keypoint_coverage`：**只对非拒答记录**求平均；缺键 / `None` / 非数值**既不进分子也不进分母**；无可用记录 → `0.0`
- `SUMMARY_FIELDS` 追加该字段；原有 7 键仍在、含义不变（**向后兼容**）
- `& $P -m compileall -q $R` 退出码 0；`& $P -m unittest discover -s "$R\tests" -t $R` 全绿（单测 **25 → 31**）
- `tests/test_offline.py` 仍不 import 任何第三方库

**成本**：0 元（mock 报告即可验收；真实评测由 T-020 一并进行）

**现状**：**已完成**。`avg_keypoint_coverage` 的契约影响登记在 **§5.13**。

---

## T-020 · 小节级整理三模式对照（`off` / `diverse` / `expand`）

| | |
|---|---|
| **难度 / 档位** | L1 / T1 |
| **依赖** | T-019（需要连续覆盖率才能测出效果） |
| **inScope** | `src/retrieve.py`、`src/config.py`、`.env.example`、`tests/test_offline.py`、`docs/**` |
| **outOfScope** | `SPEC.md`、`app/**`、`eval/**`、`data/**` |

**目标**：验证 E-02 提出的假设 —— 「检索到同一文件的**错误小节**」能否靠**按小节整理上下文**救回来。
唯一自变量是 `SECTION_MODE`，三种取值构成对照实验：

| 取值 | 含义 |
|---|---|
| `off` | 不做任何小节级整理（**默认**，与改动前行为一致） |
| `diverse` | 同一小节只保留最高分的块（**更多样、但材料更少**） |
| `expand` | 命中块所在的整个小节一起进候选（**材料更长**） |

**硬约束**：默认值必须是 `off`（未设置环境变量时行为与改动前**逐字一致**）；非法取值**不得抛异常**，回落到 `off`；`search()` 的签名与返回类型不变。

**验收**
- `SECTION_MODE` 大小写不敏感（`'DiVeRsE '` → `diverse`）、非法值回落 `off`、默认 `off`
- `expand_to_sections(hits, chunk_map)` 与 `dedupe_by_section(hits)` 为**纯函数**（不改入参）
- 三模式各跑一次真实评测（每模式 1 次，合计约 0.3 元），记录 `avg_keypoint_coverage` / `accuracy` / prompt 长度 / 截断题数
- 两条全绿命令；单测 **31 → 49**；`tests/test_offline.py` 仍不 import 任何第三方库
- 结论写入 `docs/EXPERIMENTS.md` **E-03**（无论正负）

**结论（负结果，2026-09-21）**：假设**被证伪** —— `diverse` 覆盖率 **0.5343 → 0.5147**（更差，accuracy 0.50 → 0.45）；
`expand` **0.5441**（+0.010，落在噪声内，且 **14/20 题有资料被丢**、`q04` 覆盖率 1.00 → 0.00）。
→ **默认保持 `off`**；两个模式作为**可复现实验装置**保留。详见 `EXPERIMENTS.md` **E-03** 与 `BOARD.md` 决策日志。

**成本**：约 0.3 元（三次真实评测）

---

## T-021 · 启用并真实验证 rerank（契约核对 → 对齐 → A/B → 降级验证）

| | |
|---|---|
| **难度 / 档位** | L1 / T1（Step 0 已完成；Step 2 需要花钱，须先获用户确认） |
| **依赖** | —（T-018 的结论与 T-020 的负结果共同构成本卡的动机） |
| **inScope** | `src/retrieve.py`、`src/config.py`、`.env.example`、`tests/test_offline.py`、`docs/**`、`README.md`（**补记**：初版卡面漏写 `README.md`；本卡产出的是一期唯一一个正面数字，README 的「实测结果 / 已知限制」两节必须同步，否则门面与仓库自相矛盾） |
| **outOfScope** | `SPEC.md`、`app/**`、`eval/questions.jsonl`、`eval/metrics.py`、`data/**` |

**目标**：把 rerank 从「代码写了、默认关闭、**从未联网验证过**」变成「**契约核对过、真实调用过、A/B 有数字、降级路径实测过**」。
结论**正负都算交付**；本卡**不改 `RERANK_ENABLED` 的默认值**。

**动机（有证据链，不是"顺手加个功能"）**
- E-01：融合池对多跳题**文件级 5/5 覆盖** —— 需要的内容**已经在候选里**
- E-02：`top_k` 4→8 让连续覆盖率 **5 升 0 降**（0.450 → 0.550）—— **扩大窗口有效**
- E-03：按小节整理（去重 / 整节扩展）**没有净收益** —— **排列方式不是瓶颈**
- ⇒ 三条合起来：**内容在池子里、却没进 top-k 窗口 → 这是「排序」问题**，正是 rerank 的职责

**Step 0 · 官方契约核对（✅ 已于开卡时完成，0 元）**

核对对象：阿里云百炼《文本排序》[官方文档](https://www.alibabacloud.com/help/zh/model-studio/text-rerank-api)（页面更新时间 2026-09-04）。三条结论：

| # | 结论 | 对我们的影响 |
|---|---|---|
| 1 | ✅ **字段与我们实现一致**：`gte-rerank-v2` 请求为 `{model, input:{query, documents}, parameters:{top_n}}`，响应为 `output.results[].{index, relevance_score}` | `src/retrieve.py:212-232` 的字段名**是对的**，不需要猜改 |
| 2 | ⚠️ **官方已公告 `gte-rerank` 下线、推荐改用 `qwen3-rerank`** | 我们的 `RERANK_MODEL=gte-rerank-v2` 有**生命周期风险**；且 `qwen3-rerank` 是**另一套形状**：请求扁平（`query`/`documents`/`top_n` 与 `model` 同级、无 `input`/`parameters`）、**响应 `results` 直接在顶层没有 `output`**、端点为 `/compatible-api/v1/reranks` |
| 3 | ⚠️ **端点变了**：文档现在给的是业务空间域名 `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/...` | 我们配的是老的全局域名 `https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank`，**是否仍兼容未经验证** |

> **开卡即产出的价值**：如果没做这一步就直接打开开关跑 A/B，最可能的结果是**每次调用都抛异常 → 被降级吞掉 → 报告显示"rerank 无提升"**，
> 而真实原因是**端点/模型已变**。**"降级太安静"本身就是一个必须在卡里验证的风险**（见 Step 3）。

**Step 1 · 契约对齐（0 元或几分钱，必须先于 A/B）**
1. 先做一次**最小真实连通性调用**（1 条 query + 3 条短文档，几分钱）：
   - 用**当前配置**发一次，确认老端点 + `gte-rerank-v2` 是否仍可用
   - **原始响应（脱敏）必须记录进 `docs/EXPERIMENTS.md`**，不许只写"能调通"
2. 按连通性结果二选一，**在卡内显式记录走了哪条**：
   - **A 路径（老模型可用）**：实现不动，只补 `return_documents` 的取舍说明（我们靠 `index` 回填原文，**不需要**它，可省传输）
   - **B 路径（老模型不可用）**：给 `_rerank` 补一条 `qwen3-rerank` 分支 —— 扁平请求体、顶层 `results` 解析、独立端点；
     **同时保留 gte 形状的兼容**，模型/端点由 `RERANK_MODEL` / `RERANK_URL` 驱动，不写死
3. 无论哪条路径：`MOCK=1` 时**必须一个网络请求都不发**（现有 `not self.settings.mock` 守卫），并补一条离线单测锁住它

**Step 2 · 真实 A/B（花钱，执行前须用户确认）**
- 同一套 20 题、同一份语料、同一生成模型，**唯一自变量 `RERANK_ENABLED`**（`0` vs `1`）
- 记录：`avg_keypoint_coverage`（主指标，T-019 已入报告）、`accuracy`、`partial/wrong`、`hit_rate`、`avg_latency_ms`，以及 **rerank 是否真的生效**（不能只看开关，要看响应/日志）
- **必须同时记录"有没有发生降级"**：若某次运行出现 `[warn] rerank 降级`，该次结果**不能**当作"rerank 无效"的证据

**Step 3 · 降级路径真实验证（几分钱，这张卡的安全底线）**
- 故意用**错误 key**（或错误 URL）打开 `RERANK_ENABLED=1`，在真实模式跑 1 题：
  - `search()` **不得抛异常**，必须返回**融合结果**
  - 日志/标准输出出现 `[warn] rerank 降级`
  - `/chat` 路径不受影响（接口仍返回答案）
- 这条的意义：rerank 是**可选增强**，它挂了绝不能让问答服务跟着挂 —— 这是实测而不是"设计上应该"

**通过标准（逐条可执行）**
1. `& $P -m compileall -q $R` 退出码 0；`& $P -m unittest discover -s "$R\tests" -t $R` 全绿（单测**只增不减**，当前 49）
2. `tests/test_offline.py` 仍**不 import** 任何第三方库
3. 新增离线单测：`MOCK=1` + `RERANK_ENABLED=1` 时 **`_rerank` 不被调用 / 无网络请求**（用桩或计数断言）
4. `docs/EXPERIMENTS.md` 新增 **E-04**：Step 0 的三条契约结论（含官方链接与更新时间）、连通性原始响应（脱敏）、A/B 对照表、降级验证结果
5. **A/B 对照表两个模式并排**，且明确标注"是否发生降级"
6. Step 3 的降级验证有**原始输出**（不是口头声称）
7. `RERANK_ENABLED` 默认值**仍为 `0`**；若因结论建议改默认，写进 E-04 的"建议"一节并**另开卡**
8. `git status` 不出现 `data/**`、`eval/report*.json`（本地产物）、`.env`

**成本**：连通性 + 降级验证几分钱；A/B 两次真实评测约 **0.6 元**。**合计上限 ≤ 0.8 元，执行 Step 2 前需用户明确确认。**

**红线**
1. 禁止硬编码 key；key 只走环境变量，用完即清的临时脚本不得入库
2. 禁止把"rerank 被降级吞掉"的结果当成"rerank 无效"的证据
3. 禁止为了让 rerank 生效而放宽 `SPEC.md §5` 的 `max_chars`、改题库或改判分口径
4. 禁止在本卡顺手改 `TOP_K_FINAL` 默认值（那是另一张卡的证据范围）
5. 禁止把 20 题单次运行的差异（尤其 < 0.03 的覆盖率差）说成"提升"——按 `§5.5` 报区间与逐题升降

**结论（正面结果，2026-09-21）**：**rerank 有效，但默认值不改** ——
主指标 `avg_keypoint_coverage` **0.5490 → 0.6373（+0.088）**、`wrong_rate` **0.20 → 0.10**、逐题 **升 4 / 降 1**（`q14` 变差必须主动说）；
代价是单题延迟 **1136 → 3188 ms（+2.05 s）**。三条"确实生效"的证据：`_rerank` 被调 20 次 0 异常、**20/20 题顺序被改变**、输出全部来自融合池（0 违反）。
Step 1 走 **A 路径：`src/retrieve.py` 零改动**（老端点 + `gte-rerank-v2` 实测 200，字段与实现一致）；
官方公告的替代模型 `qwen3-rerank` 在同一端点上**用同一套 body 也 200**，可纯靠 `RERANK_MODEL` 切换。
详见 `EXPERIMENTS.md` **E-04** 与 `PLAN.md §5.15`。

**结论模板**

```
任务：T-021 启用并真实验证 rerank
改动文件：`tests/test_offline.py`、`docs/EXPERIMENTS.md`、`docs/PLAN.md`、`docs/BOARD.md`、`README.md`（`src/**` **零改动**）
验收结果：
  [x] compileall 退出码 0 —— 实际：compileall exit=0
  [x] 离线单测全绿（Ran N tests, OK）—— 实际：Ran 52 tests / OK（49 → 52，纯新增 121 行、0 删除）
  [x] MOCK=1 不发请求的离线单测 —— 实际：`RerankGuardTests.test_mock_mode_never_calls_rerank`；变异反证：删掉 `not self.settings.mock` 后该用例 FAIL
  [x] Step 1 连通性：走了 **A 路径**，原始响应见 E-04 §2 —— 实际：P1 HTTP 200 `output.results[0].relevance_score=0.8512...`；P3 扁平路径 404
  [x] Step 2 A/B 对照表（含是否降级）—— 实际：覆盖率 0.5490 → 0.6373，延迟 1136.2 → 3187.9，`_rerank` 调用 20 / 异常 0
  [x] Step 3 降级验证（原始输出见 **E-04 §6**）—— 实际：错 key → `401 Client Error` → 打出 `[warn] rerank 降级` → 不抛异常 → 结果与融合结果逐字一致；`/chat` 补测 HTTP 200 且返回答案
  [x] RERANK_ENABLED 默认仍为 0 —— 是（`.env.example` 与 `config.py` 均未改）
遗留问题：① `q14` 变差（0.500 → 0.250），rerank 非单调改进；② 静默降级是运维陷阱（"没效果"可能只是降级了）；
        ③ `qwen3-rerank` 的兼容嵌套 body 是实测行为、非文档承诺；④ 默认值、`TOP_K_FINAL`、`RERANK_MODEL` 切换均未做（属新卡）
下一步建议：若要在线启用，先做「延迟换质量」的取舍决策卡（`RERANK_ENABLED` 默认值 + 超时/降级可观测性）
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
6. **`multi_hop` 是当前最弱项；瓶颈位置经复盘**修正**为「小节级检索精度」**（见 `docs/EXPERIMENTS.md` **E-02**，它**推翻了 E-01 的结论**）：
   分类实测 `multi_hop` accuracy **0.20**（5 题：1 完全对 / 3 部分对 / 1 错）、`single_hop` **0.50**（12 题：6/2/4）、`unanswerable` **1.00**（3 题全部正确拒答）。
   - **文件级召回没问题**：融合池 **5/5** 覆盖全部 `gold` 文件；top-4 截断只影响 5 题里的 2 题
   - **但不是"生成侧"的问题**（E-01 曾如此判断、**已被 E-02 推翻**）：模型答"资料里没有"时，检索给它的上下文里**确实没有** —— 它的回答是诚实的，既非幻觉也非能力不足
   - **真正的瓶颈是「检索到同一文件的错误小节」**：`q03`/`q12`/`q14`/`q16`/`q17` 缺的内容**全在语料里**，只是给模型的是**错的节**
   - `TOP_K_FINAL` 4→8 **有真实效果、只是被桶指标隐藏**：逐题 keypoint 覆盖率 **5 升 0 降**（多跳均值 0.450→0.550，**p ≈ 0.031**），但没跨过 0.8 的桶阈值
   - `q02`/`q12`/`q13`/`q17` 连 `top_k=8` 都没救 → 需要**把命中块所在的小节一起给模型**（父子分块的最小形态），而不是继续加大 k
   - **`hit_rate` 不能跨 k 比较**：`hit_at_k` 是「**任一**命中即算」且**对 k 单调**，k 变大命中率机械上升（V2 的 `0.80→0.85` 不是质量提升）
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
12. **向量检索层的结果不可跨进程复现（T-015 过程中发现）**：chroma 的 HNSW 近似检索，同一份代码、同一份索引，在不同进程里对同一 query 返回的候选集与排序**会漂移**。
    证据：以改动前抓的黄金基线为准，**未改动的原版代码**同样对不上（实测 10 / 6 处差异），而同一份代码跨进程连跑时 `vector` 层也会变化；`bm25` 层则**始终**稳定（说明 `chunks.jsonl` 没变）。
    **影响**：任何依赖检索的指标（尤其 `hit_rate`）都带这一层不确定性。实测中 `hit_rate` 三次真实评测都稳定在 **0.80**，但那是"**指标层稳定**"，**不等于**"每次召回的 chunk 排名一致"。
    **引用方式**：可以报 `hit_rate 80%`，但若被追问"逐次召回是否完全相同"，要答"不是"。
    **可能的方向**（未开卡）：给 chroma 的 HNSW 设置单线程 / 调 `search_ef`，或改为精确检索；但这属于检索层重构，超出 T-015 的范围。
13. **汇总字段清单是对 `SPEC.md` 的「向后兼容扩展」（T-019，代码已落地）**：`eval/run_eval.py` 的 `SUMMARY_FIELDS` 在既有 7 个字段（`n / accuracy / partial_rate / wrong_rate / refusal_accuracy / hit_rate / avg_latency_ms`）**之后追加**了
    `avg_keypoint_coverage` —— **非拒答记录**的逐题连续 keypoint 覆盖率均值（0~1；拒答题 `keypoints` 为空、计入只会拉低均值故排除；没有可参与求平均的记录 → `0.0`）。
    它**只新增、不改名、不删除、不改语义**，所以对既有消费方是**向后兼容**的（原有 7 键仍在、含义未变）。
    - **理由**：桶指标（阈值 0.8）**不灵敏**。`docs/EXPERIMENTS.md` **E-02** 用同一批既有数据证明：桶指标把「覆盖率 **0.450 → 0.550**、逐题 **5 升 0 降**（**p ≈ 0.031**）」压成了"一分未动"，于是得出了**相反**的结论。连续指标必须由**报告本身**给出，否则每次对照都要靠临时脚本回读逐题明细 —— **先修仪器，再改系统**。
    - **与 SPEC 的关系**：`SPEC.md` 第 318 行列的汇总字段清单因此比实现**少一项**。严格讲这**不等于 SPEC 原文**；而 `§0.2` **禁止修改 `SPEC.md`**，故本卡按「实现扩展 + 在此登记」处理，不改契约文件。
    - **若要写进 `SPEC.md`**：需**用户批准解除 `§0.2` 的「不得修改 `SPEC.md`」限制**（另开一张文档卡；本卡不碰 `SPEC.md`）。

14. **小节级整理（`SECTION_MODE`）实测无效，默认保持 `off`（T-020，2026-09-21）**：新增的环境变量 `SECTION_MODE` 有三档 —— `off`（默认，行为与改动前逐字一致）/ `diverse`（同一小节只留最高分块）/ `expand`（命中块所在小节整节进候选）。
     唯一自变量、三次真实评测的实测结果：

     | 指标 | `off` | `diverse` | `expand` |
     |---|---|---|---|
     | `avg_keypoint_coverage` | 0.5343 | **0.5147 ↓** | 0.5441（噪声内） |
     | `accuracy` | 0.50 | **0.45 ↓** | 0.50 |
     | prompt 中位 / 最大（字符） | 1624 / 1936 | 1465 / 1936 | **2388 / 4742** |
     | 有资料被 3000 字符预算丢掉的题数 | **0** | **0** | **14 / 20** |
     | 其中"最终 prompt 仍超 3000"的题 | 0 | 0 | **4**（`q04`/`q07`/`q11`/`q14`） |

     - **假设被证伪**：E-02 定位到「检索到错误小节」，但**按小节整理救不回来** —— 说明瓶颈不是"材料的组织方式"
     - **`diverse` 反而更差**：按小节去重**减少了进入上下文的块数**（材料 4 → 2~4 条），换来的"小节多样性"补不回丢掉的内容
     - **`expand` 不能当默认**：覆盖率 +0.010 落在 §5.5 的波动范围内（升 2 / 降 1），代价却是 **14/20 题丢资料**；
       而且 `build_prompt` 是"第一条塞不下就 `break`"，所以第 2 条小节过长时模型只剩很小的第 1 条（`q05` 346 字符、`q09` 200 字符），`q04` 覆盖率 1.00 → 0.00
     - **合起来的主结论**：`top_k` 4→8（内容更多）有效、`diverse`（内容更少）更差、`expand`（更长但被截断）持平 —— **决定成败的是"上下文里有没有那段内容"**
     - **口径说明**：prompt 长度与丢资料题数**不在**评测报告里（逐题明细无该字段），来自一次**只跑检索、不调 LLM** 的本地复算
       （比较 `build_prompt(max_chars=0)` 与 `max_chars=3000`，成本仅 60 次 query embedding）；
       `vector` 层跨进程会漂移（§5.12），故 prompt 数字读作**量级**，而"十几道题丢资料"由小节字数决定、对漂移不敏感
     - **怎么引用**：可以说「试过小节级去重与整节扩展两种整理方式，实测都没有净收益，因此默认关闭」；**不要说**"解决了多跳问题"或"提升了检索精度"
     - **代码为何留着**：它是一个**可复现的实验装置**，换语料 / 换 `top_k` 时可一键重跑对照；`SECTION_MODE` 只新增、不改任何既有签名
     - **派生发现（已登记、未修）**：`Retriever.debug()` 返回的 `final` 仍是「未整理」的 top-k，**不反映 `section_mode`**。
       默认 `off` 时两者一致，故无实际影响；但它是 T-020 引入的**潜在不一致**（此前 `final` 就等于最终结果）。
       修它要动 `debug()`，超出本卡卡面（只改 `search()` 路径），因此只登记
     - **遗留矛头（已由 T-021 接手并验证）**：`src/retrieve.py` 的 rerank 路径当时**已实现但 `RERANK_ENABLED=0` 从未启用、也从未用真实 API 验证过**。
       E-01/E-02/E-03 共同指向**排序**而非召回 —— **T-021 已完成该验证**（结论见 §5.15 与 `EXPERIMENTS.md` E-04：
       全库 +0.088 有效，**但对多跳题零效果**，代价 +2.0 s）

15. **rerank 实测有效，但对多跳题零效果；默认仍关闭；代价是每题约 +2 s（T-021，2026-09-21）**：同进程 A/B（唯一自变量 `use_rerank`，见 `EXPERIMENTS.md` **E-04**）
    的主指标 **`avg_keypoint_coverage` 0.5490 → 0.6373（+0.088）**、`wrong_rate` **0.20 → 0.10**、逐题 **升 4 / 降 1**；
    代价是单题延迟 **1136 → 3188 ms（+2.05 s）**。
    - ⚠️ **按题型拆开后结论减半（必须与上面的数字一起说）**：`single_hop` 覆盖率 **0.5694 → 0.6944（+0.125）**、桶内 5/4/3 → 6/5/1；
      **`multi_hop` 覆盖率 0.5000 → 0.5000（±0.000）**、桶内 **1/3/1 → 1/3/1 完全没变**（`q16` +0.25 与 `q14` −0.25 精确抵消）。
      **收益全部来自单跳题。** 而本卡与 E-01~E-03 的动机都是**多跳** ⇒ **多跳的瓶颈仍未找到**；
      已被逐一排除的有：文件级召回、窗口大小（部分有效）、材料排列、全局重排
    - **怎么引用**：说「rerank 让全库主指标 +0.088、`wrong_rate` 腰斩，**但对多跳题零效果**；代价 +2.0 s，所以默认关闭」。
      **不要**说"提升了 8.8 个百分点"（n=20 单次运行、不是统计检验）·**不要**说"解决了多跳问题"·**不要**只报总体数字而不提分题型
    - **`RERANK_ENABLED` 默认值保持 `0`**：收益偏质量、成本偏延迟，应由使用方按场景权衡（离线批量评测 vs 在线问答），
      且 `SPEC.md` 把 rerank 列为**二期可选**。改默认值是**另一张卡 + 用户批准**的事 —— 已在 `BOARD.md` 决策日志里预先写死这条红线
    - **静默降级是这里最大的运维陷阱**：`_rerank` 的任何异常都被 `search()` 吞掉、只 `print("[warn] rerank 降级: ...")`。
      好处是服务不会挂（已实测：错 key → 401 → 降级 → 结果与融合结果逐字一致，`/chat` 仍 200）；
      **代价是"rerank 没效果"这种结论可能只是降级了**。⇒ 任何基于 rerank 的对比实验，**必须先确认没发生降级**
      （E-04 用调用计数 + 顺序改变 + 候选集不变式三条证据）
    - **模型生命周期风险**：官方文档（2026-09-04 更新）已公告 **`gte-rerank` 下线、推荐 `qwen3-rerank`**。
      实测老服务端点**仍接受** `qwen3-rerank` + 我们的嵌套 body（HTTP 200），故**可以纯靠 `RERANK_MODEL` 切换、无需改代码**；
      但**官方文档给的是扁平形状**（`results` 在顶层、`/compatible-api/v1/reranks`），
      即这个兼容性属**实测行为、不是文档承诺** —— 老端点哪天改掉，表现又会是"rerank 没效果"（同上一条的陷阱）
    - **`relevance_score` 不可跨请求比较**：官方明确它是**当前请求内的相对分**。我们的实现只在一次请求内排序，符合该约束；
      但**不要**把它当成可跨题、跨运行的质量分来报
    - **本实验的数字不能与 `report.json` 直接比**：同进程设计排除了向量漂移（这是优点），代价是基线 `0.5490`
      与 T-020 的 `0.5343` 之间的差异来自**进程/召回/LLM 波动**，不是"改了什么东西"
    - **这已经是「粒度决定你能看见什么」的第三次重演**：第一次是文件级/桶级/连续值（E-02），
      第二次是"截断"的两种口径（E-03），这次是**总体 vs 分题型** ——
      总体看是成功、分题型看目标（多跳）**没达成**。**只报总体数字 = 用一个成功的外壳掩盖没达成的目标**
    - **未做的事（都属新卡）**：`RERANK_ENABLED` 默认值、`TOP_K_FINAL` 4→8、
      **`top_k` 与 rerank 联合调参**（E-02 说"窗口更大对多跳有效" + E-04 说"重排对多跳无效" ⇒ 这个假设最值得先测：
      让 rerank 只做排序、不替多跳题做取舍）、**保证跨文档覆盖的排序**（按 `source` 限席位，与 rerank 的单 query 相关性正交）、
      `RERANK_MODEL` 默认切到 `qwen3-rerank`

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
| 2026-09-18 | 新增 T-015（缓存检索索引，M5 性能优化）并**修正其验收标准第 1 条** | 实测发现每次检索都重建 BM25 索引（占检索耗时 99%）；而初版验收写的"跨进程黄金基线逐字 diff"被证明**天生不可达**——未改动的原版代码同样对不上（10/6 处差异），差异全在 vector 层。改为**同进程 A/B**（两条路径共享同一 chroma 状态，差异只可能来自缓存），在相关维度上更严格 |
| 2026-09-18 | 新增 T-016（multi-hop 检索侧对照实验），**以负结果收尾**，并新建 `docs/EXPERIMENTS.md` | 外部建议"先修 multi-hop（父子分块或调 top_k_final）"，但项目此前**没有做对照的能力与习惯**。实验证明：候选从 4 扩到 8 后 `multi_hop` 一分未动，而融合池本来就 5/5 覆盖全部依据 → **瓶颈在生成侧**，检索侧改动无效。同时发现 `hit_at_k` 对 k 单调、不能跨 k 比较质量 |
| 2026-09-18 | 新增 T-017（修正 `$K` 路径） | 工作区整理把 `agent-project-kit/` 移到了根目录，`§0.2` 的 `$K` 变成死路径，T-016 提交时实际撞到 `MODULE_NOT_FOUND`。已在 §0.2 补「找不到时怎么定位」——因为它是**仓库外的本机路径**，会反复失效 |
| 2026-09-18 | 新增 T-018（修正 E-01 的错误结论）；**确立「主指标用连续覆盖率」** | E-01 用判分桶比较，把「覆盖率 0.450→0.550、5 升 0 降」压成了"一分未动"，于是得出了**相反**的结论。同一批数据在文件级 / 桶级 / 连续值三种粒度下给出三个互相矛盾的答案 —— **粒度决定你能看见什么**。今后所有对照实验的主指标改为**逐题连续 keypoint 覆盖率**，桶指标仅作汇报 |
| 2026-09-21 | 新增 T-019（把**连续 keypoint 覆盖率**接进评测报告）：`run_once` 新增记录键 `keypoint_coverage`、`aggregate` 新增 `avg_keypoint_coverage`、`SUMMARY_FIELDS` 追加同名汇总字段；并在 **§5.13** 登记这是对 SPEC 汇总字段清单的**向后兼容扩展** | E-02 的教训是**仪器不够细**：桶指标把 0.450→0.550 压成"一分未动"。补救办法不是每次写临时脚本回读逐题明细，而是让**报告天生带连续覆盖率** —— **先修仪器，再改系统**（下一步 T-020 的小节级上下文才有可用的对照指标）。新增字段只追加不改名，故向后兼容；`SPEC.md` 按 §0.2 不动，写进 SPEC 需用户批准 |
| 2026-09-21 | T-019 收尾（**待审 → 完成**），并补齐 T-019 / T-020 两张**正式任务卡**（此前只在里程碑表里跟踪） | T-019 的代码与验收在 2026-09-21 已完成并登记进 §5.13；补卡是为了让「每个任务自带验收标准」这条不被自己破例 —— 里程碑表回答"做没做"，任务卡回答"做到什么算完" |
| 2026-09-21 | 新增 **T-020**（小节级整理三模式对照，M8）并**以负结果收尾**；`SECTION_MODE` 默认值定为 **`off`** | E-02 定位到「检索到同一文件的错误小节」，于是提出"按小节整理能否救回来"这个假设。三次真实评测**证伪了它**：`diverse` 更差（0.5343→0.5147）、`expand` 仅在噪声内（+0.010）且让 14/20 题丢资料。**按证据不改默认值** —— 改默认值需要正面证据，这是 T-016 立下的规矩，不因这次是自己写的代码而放宽。负结果与三个实验的合流结论记录在 §5.14 与 `EXPERIMENTS.md` E-03 |
| 2026-09-21 | 新增 **T-021**（启用并真实验证 rerank，M9）；**Step 0 官方契约核对已在开卡时完成（0 元）** | E-01/E-02/E-03 三个实验把矛头收敛到**排序**：内容在融合池里、却没进 top-k 窗口。而 `src/retrieve.py:203-288` 的 rerank **实现了、默认关闭、从未联网验证**，是唯一一条"有证据支持但没数字"的路。核对官方文档后发现**不能直接开开关就跑**：字段名虽与我们一致，但**官方已公告 `gte-rerank` 下线、推荐 `qwen3-rerank`（另一套请求/响应形状）**，且文档端点已改成业务空间域名。若不做这一步，最可能的结果是"每次调用抛异常 → 被降级静默吞掉 → 报告显示 rerank 无提升"，而真实原因是契约变了。故本卡把「契约核对 → 连通性 → 对齐 → A/B → **降级路径实测**」串成一条链，并明确 **`RERANK_ENABLED` 默认保持 `0`** |
