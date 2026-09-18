# 项目任务书 · TASK_BRIEF

> 唯一真相源。Agent 每次开工前必读。
> 写法铁律：**每条都要能被验证**。写不出验证方式的，就是没想清楚。
>
> 本文件由 T-011 按 `SPEC.md`（需求契约）+ `docs/PLAN.md`（执行计划）反推补齐。
> **冲突时优先级：`SPEC.md` > `AGENTS.md` > 本文件 > `PLAN.md`。**

## 1. 背景与目标

**要解决什么问题**：把一堆本地文档（`.md` / `.txt` / `.pdf`）变成一个能问答、**能说出答案出处**的最小 RAG 服务，并在自建评测集上产出**可复现、可量化**的质量数字。对作者而言，这是求职简历上「AI 应用方向」唯一的项目证据——现有简历只有软件测试与后端课程项目，没有 AI 工程证据，用「熟练使用 AI 工具」顶替不了。

**为什么现在做**：2027 届秋招正在进行（互联网正式批 9 月中下旬至 10 月上旬陆续截止）。没有可演示项目 + 真实数字，投 AI 应用岗基本是无效投递；而「简历上有一个真跑出来的准确率」这件事，越早做完越早能开始投。

**目标用户**：

- **作者本人**：面试时需要在 3 分钟内讲清「为什么这么切分 / 为什么混合检索 / 数字怎么来的」，并被追问三层不心虚。
- **面试官 / HR**：打开仓库 5 分钟内能看懂项目在做什么、怎么跑、数字是多少。

**成功的样子（可量化）**：

1. `MOCK=1` 下零成本、零 API key 跑通「入库 → 检索 → 生成 → 评测」全链路，退出码全 0。
2. 20 题自建评测集产出 `accuracy` / `partial_rate` / `wrong_rate` / `refusal_accuracy` / `hit_rate` / `avg_latency_ms` **六个真实数字**，原样记入 `docs/BOARD.md`（不许润色）。
3. clone 仓库后，按 `README.md` 的命令能复现 1 与 2。

## 2. 范围

### 2.1 范围内（做什么）

- 支持 `.md` / `.txt` / `.pdf` 语料入库：切分 → 向量化 → Chroma 本地持久化
- 提供混合检索：向量召回 + BM25 关键词召回 → RRF 融合（可选 Rerank 重排）
- 用 OpenAI 兼容端点生成**带 `[编号]` 出处**的回答；资料不足时必须明确拒答
- 提供 FastAPI 服务：`GET /health`、`POST /ingest`、`POST /chat`
- 提供 20 题评测 CLI，输出机器可读的报告 JSON
- 维护一套**纯标准库**的离线单测，保证没有第三方包时也能验证核心契约

### 2.2 范围外（不做什么）

- 不做前端页面、登录鉴权、多用户、Redis 缓存
- 不引入 LangChain / LlamaIndex —— 一期手写链路，保证每一层都可解释
- 不做微调 / 训练、不做向量数据库集群、不做 Docker / K8s、不做异步任务队列
- 不提交第三方版权语料到仓库
- 不在本仓库内实现治理套件脚本（`push-task.mjs` 等属外部工具）

### 2.3 后续再说（明确推迟）

- 极简前端问答页（SSE 流式输出）
- Agent Function Calling 多工具调用与多轮记忆
- 多路召回、父子分块、query 改写、HyDE

## 3. 功能清单与验收标准

| # | 功能 | 验收标准（可验证） | 优先级 |
|---|---|---|---|
| F1 | 语料入库 | `MOCK=1` 下 `python -m src.ingest` 退出码 0，输出含 `files` / `chunks` / `mocked`；`data/chunks.jsonl` 行数 = 输出的 `chunks`；`data/chroma/` 存在 | P0 |
| F2 | 混合检索 | 同一 query 能分别拿到 `vector` / `bm25` 结果，融合结果按 RRF 分降序且 chunk id 不重复（`Retriever.debug()` 四键齐全） | P0 |
| F3 | 带引用生成 | 回答末尾含 `[编号]`，且编号能在本次 `hits` 中找到；`hits` 为空时回答「根据现有资料无法回答」 | P0 |
| F4 | HTTP 服务 | `GET /health` 返回 `status`/`mock`/`chunks`；`POST /chat` 传空 `question` 返回 **400**；检索为空时不返回 500 | P0 |
| F5 | 评测 CLI | `python -m eval.run_eval --mode mock --questions ... --out ...` 退出码 0，报告含 `n` 与六个指标键 | P0 |
| F6 | 离线可验证 | `compileall` 退出码 0；`unittest discover` 全绿且测试**不 import** 任何第三方库 | P0 |
| F7 | 真实模式评测 | 非 mock 模式跑完 20 题，`report.json` 六个指标齐全，数字原样记入 `docs/BOARD.md` | P1 |

优先级说明：P0 = 没有就不能算跑通；P1 = 重要但需要凭据/费用才能验收。

## 4. 技术约束

| 项 | 约束 |
|---|---|
| 语言与版本 | Python **3.12.0**，唯一允许的解释器：`C:\Users\a2695\AppData\Local\Programs\Python\Python312\python.exe`；**禁止**使用机器上的 Anaconda Python 3.7 |
| 框架 | FastAPI 0.141.1 + uvicorn 0.53.0；`openai` 3.15.0（OpenAI 兼容端点，同时用于 Embedding 与生成） |
| 数据与存储 | ChromaDB 1.5.9 本地持久化（`data/chroma/`）；切块落盘 `data/chunks.jsonl`；**禁止**引入 Redis 或其他向量库 |
| 运行环境 | Windows 本地；沙箱内 `PATH` 为空串，**所有命令必须写绝对路径**（`python` / `node` / `git`） |
| 必须复用 | `src/config.py` 的 `load_settings()` 作为配置唯一入口；`eval/metrics.py` 作为判分口径唯一实现 |
| 禁止使用 | LangChain / LlamaIndex / 任何微调框架；第三方库**只能延迟导入**（例外：`app/main.py` 可顶层 `from fastapi import FastAPI`） |

## 5. 非功能要求

- **性能**：单条问答在真实模式下观测 `latency_ms`（受模型 API 影响，**仅观测不设门槛**）；mock 全链路 < 30 s
- **安全**：任何真实 key 只允许存在于 `.env`（已 gitignore）或环境变量；`.env.example` 只留占位与默认端点
- **兼容**：Python 3.12；中文文件名与 CJK 路径必须正常处理（写入一律 `encoding="utf-8"`）
- **可维护性**：核心契约（切分 / 融合 / 判分 / 配置）必须有离线单测覆盖；`tests/test_offline.py` 不得 import 第三方库
- **可观测**：`/chat` 返回 `latency_ms`；评测报告含 `avg_latency_ms`

## 6. 里程碑

| 里程碑 | 交付内容 | 验收方式 |
|---|---|---|
| M1 | mock 模式下全链路跑通（零成本、零 key） | `PLAN.md` T-007 的四条命令 + 反作弊探针（3 题题库 → `n=3`） |
| M2 | 真实模式 20 题评测产出报告 | `PLAN.md` T-009 的两条命令 + `report.json` 六指标齐全 |
| M3 | 下一会话可无缝接续 | `PLAN.md` T-010：README 每条命令本轮实跑过、BOARD 无失实状态 |

## 7. 假设与风险

| 假设 / 风险 | 若不成立的影响 | 应对 |
|---|---|---|
| `openai==3.15.0` 与代码里的 1.x 风格用法兼容 | 真实模式全挂 | 已静态核对 `client.embeddings.create` / `client.chat.completions.create` 存在；**T-009 前先做一次最小真实调用**再批量跑 |
| `chromadb==1.5.9` 的 `query()` 返回结构与 `src/store.py` 的假设一致 | 检索结果错位或抛异常 | 已在 `MOCK=1` 下实跑通（`fused 12 → final 4`）；真实 embedding 下待复验 |
| `data/raw/` 语料只有 1 份 | 20 题覆盖面不足，数字不具说服力 | 需用户补齐语料（T-006 卡在用户） |
| 真实评测产生 API 费用（约 ¥2–20） | — | 先 mock 后真实；T-009 执行前需用户确认 |
| 指标难看就想改题 / 改 `keypoints` | 数字失真，面试一追就崩 | `PLAN.md` T-009 红线：改题作废重来 |
| `MOCK=1` 仍需要 `chromadb` | "不花钱跑通"也得先装依赖 | 已于 T-004 解决，依赖已装且版本已 pin |

## 8. 待确认问题

- [ ] `data/raw/` 的语料由谁提供、何时到位？（T-006 依赖用户）
- [ ] 真实评测的费用是否已确认？T-009 执行前需要明确答复
- [ ] `openai==3.15.0` 的真实调用兼容性，需要一次最小请求验证（建议并入 T-009 的第一步）
- [ ] 治理矛盾已由 T-011 修掉两处（`PLAN.md §3` 的 `push-task.mjs` 路径、DoD 与 outOfScope 的冲突）；若后续还发现，一并记在这里
