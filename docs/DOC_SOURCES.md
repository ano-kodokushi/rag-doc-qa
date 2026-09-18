# 文档来源登记（docs/DOC_SOURCES.md）

本文档分两态登记 `data/raw/` 的语料：**已入库**（含精确来源与校验和）与**待补**。
`SPEC.md §7` 建议一期 10 份，当前已入库 **12 份**（含 1 份自有文档）。

> **版权**：第三方官方文档仅本地离线检索使用，**不提交公开仓库**——`data/raw/*` 被 `.gitignore` 忽略，
> 只放行 `data/raw/README.md` 与 `data/raw/00_*.md`（自有项目文档）。见 §4。

---

## 一、已入库语料清单（2026-09-18 抓取）

抓取方式：从各项目官方文档仓库下载**原始 Markdown 字节**，未做任何二次加工
（保留 `#` 标题层级，便于按标题切块）；`sha256` 前缀用于复核来源未被篡改。

### 1.1 自有文档

| # | 文件名 | 字节 | sha256(前12) | 来源 |
|---|---|---|---|---|
| 00 | `00_保洁系统_项目说明.md` | 4211 | `3ee14f948893` | 本地：由 `简历用图/README_简历配图说明.md` 复制（⚠️ 内容与文件名不符，见 §5.2） |

### 1.2 第三方官方中文文档（不入库）

| # | 文件名 | 字节 | sha256(前12) | 来源 URL |
|---|---|---|---|---|
| 01 | `01_Vue3_快速上手.md` | 15684 | `75760850c416` | https://raw.githubusercontent.com/vuejs-translations/docs-zh-cn/main/src/guide/quick-start.md |
| 02 | `02_Vue3_响应式基础.md` | 19682 | `34ad3944ca85` | https://raw.githubusercontent.com/vuejs-translations/docs-zh-cn/main/src/guide/essentials/reactivity-fundamentals.md |
| 03 | `03_Vue3_组件基础.md` | 23994 | `ae7ccdd764b3` | https://raw.githubusercontent.com/vuejs-translations/docs-zh-cn/main/src/guide/essentials/component-basics.md |
| 04 | `04_Vue3_计算属性.md` | 11295 | `52a4897eadde` | https://raw.githubusercontent.com/vuejs-translations/docs-zh-cn/main/src/guide/essentials/computed.md |
| 05 | `05_Vue3_组合式函数.md` | 18509 | `a14814d559a6` | https://raw.githubusercontent.com/vuejs-translations/docs-zh-cn/main/src/guide/reusability/composables.md |
| 06 | `06_FastAPI_快速入门.md` | 14085 | `a23971126203` | https://raw.githubusercontent.com/fastapi/fastapi/master/docs/zh/docs/tutorial/first-steps.md |
| 07 | `07_FastAPI_路径参数.md` | 8044 | `a008badf3fd5` | https://raw.githubusercontent.com/fastapi/fastapi/master/docs/zh/docs/tutorial/path-params.md |
| 08 | `08_FastAPI_查询参数.md` | 4262 | `c1f6d59f65f0` | https://raw.githubusercontent.com/fastapi/fastapi/master/docs/zh/docs/tutorial/query-params.md |
| 09 | `09_FastAPI_请求体.md` | 6053 | `849918c18b76` | https://raw.githubusercontent.com/fastapi/fastapi/master/docs/zh/docs/tutorial/body.md |
| 10 | `10_FastAPI_教程总览.md` | 24385 | `fb69e2e097ce` | https://raw.githubusercontent.com/fastapi/fastapi/master/docs/zh/docs/index.md |
| 11 | `11_MyBatis-Plus_官方文档导读.md` | 3224 | `c44c6956cb0d` | https://raw.githubusercontent.com/baomidou/mybatis-plus-doc/master/README.md |

**为什么选这几份**：全部是**中文**，且覆盖本项目实际技术栈（Vue 3 是自有项目前端、FastAPI 是本服务框架、
MyBatis-Plus 是自有项目后端 ORM）。按 `§3.1` 的取舍，只抓需要的章节，不拖整站。

**复核方式**：重新下载上表 URL，用原始字节的 sha256 与本地文件比对，应完全一致。
完整 64 位校验和可用 `Get-FileHash <文件> -Algorithm SHA256` 现场取得。

---

## 二、待补语料（自有项目文档）

`SPEC.md §7` 列为评测题**主要依据**，目前**缺失**。请从你自己的项目仓库/文档系统整理：

| 文档 | 内容要点 | 状态 |
| --- | --- | --- |
| 需求说明 | 角色、业务流程、功能列表 | ❌ 未补 |
| 数据库设计 | 表结构、字段含义、索引与约束 | ❌ 未补 |
| 接口文档 | 路径、入参、出参、错误码 | ❌ 未补 |
| 部署文档 | 环境要求、启动方式、配置项 | ❌ 未补 |
| 订单状态机说明 | 状态枚举与流转规则（多跳题常用） | ❌ 未补 |

建议整理成 Markdown，文件名加数字前缀（例如 `12_保洁系统_需求说明.md`）。
自有文档建议命名以 `00_` 开头可被 `.gitignore` 放行；若希望入库，
请同步调整 `.gitignore` 的放行规则并在本文件登记。

---

## 三、官方入口（备用，供后续补充章节时手动下载）

| 主题 | 官方入口 |
| --- | --- |
| Spring Boot | https://spring.io/projects/spring-boot ／ 中文译文 https://springdoc.cn/spring-boot/ |
| MyBatis-Plus | https://baomidou.com/ |
| Vue 3 | https://cn.vuejs.org/ |
| MySQL | https://dev.mysql.com/doc/ ／ 中文 https://www.mysqlzh.com/ |
| Redis | https://redis.io/docs/latest/ ／ 中文 https://redis.com.cn/ |

> **具体地址以官方文档为准，请自行核对。** 官方站点结构可能调整，上表仅为入口指引。

**抓取与整理建议**

1. 只抓**需要的章节**，不要把整站拖下来——语料过大会稀释检索精度，切块也会变慢。
2. 抓成 Markdown 时保留标题层级（`#`/`##`），切块按标题走效果最好。
3. 页面里的导航、页脚、广告请删掉，它们会成为噪声命中。
4. 同一主题只保留一份，避免中文版 + 英文版重复导致检索结果重样。
5. 下载后再次核对：文件能正常打开、编码是 UTF-8、PDF 不是扫描件。

---

## 四、版权与提交注意

- 第三方官方文档**不要提交到公开仓库**，仅本地离线检索使用。
- `.gitignore` 的实际规则是：`data/raw/*` **全忽略**，另用 `!` 放行两条 ——
  **`data/raw/README.md`**（语料说明）与 **`data/raw/00_*.md`**（自有项目文档）。
  即：自有文档入库、第三方文档不入库。
- 引用官方文档做评测时，评测集里只需写文件名（`gold_sources`），无需复制原文。
- 本项目自有文档若含敏感信息，请先脱敏再放入 `data/raw/`。

---

## 五、已知限制（影响 T-008 出题，必须知悉）

### 5.1 FastAPI 语料缺少代码示例（medium）

FastAPI 官方文档在源码里用 MkDocs 宏引用代码文件，例如
`{* ../../docs_src/first_steps/tutorial001_py310.py *}`，
构建站点时才会把代码内联进去。因此直接从仓库抓原始 Markdown 时，**代码示例全部缺失**：

| 文件 | 未展开的 include 处数 |
| --- | --- |
| `06_FastAPI_快速入门.md` | 7 |
| `07_FastAPI_路径参数.md` | 10 |
| `08_FastAPI_查询参数.md` | 6 |
| `09_FastAPI_请求体.md` | 6 |
| 合计 | **29** |

**对 T-008 的要求**：出题**回避代码示例类题面**（如「这段代码怎么写」「该路由的响应模型是什么」
「请求体字段长什么样」）——语料里没有依据，只会命中断言式散文，导致正确率失真且无法归因。
只出**概念、名称、参数语义**类题目。
若要补齐代码，需另开卡从 `fastapi` 仓库 `docs_src/` 抓 `.py` 源码并另存为 `.md`/`.txt` 语料
（注意 `src/ingest.py` 只读 `.md` / `.txt` / `.pdf`，`.py` 不会被入库）。

### 5.2 `00_保洁系统_项目说明.md` 内容与文件名不符（low，跨卡遗留）

该文件首行是「# 简历配图 · 上门保洁服务系统」，正文是**简历配图顺序与图注建议**，
并非需求 / 库表 / 接口 / 部署 / 状态机文档。它由早于 T-006 的提交引入，**非本卡新增**，故只登记不修改。

**为什么不改名**：`SPEC.md §7` 明确以 `00_保洁系统_项目说明.md` 这个文件名登记它，
而 `SPEC.md` 是最高优先级契约、不得修改。改名会让契约与仓库不一致。
真正的自有文档（§二）补进来后，本文件可降级为附属材料。
