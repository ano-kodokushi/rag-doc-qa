# 建议文档来源（docs/DOC_SOURCES.md）

本文档列出**建议**放入 `data/raw/` 的文档及其官方入口，供手动下载。
下载后请自行转成 `.md` / `.txt` / `.pdf`（见 `data/raw/README.md`）。

> **具体地址以官方文档为准，请自行核对。** 官方站点结构可能调整，下列 URL 仅为入口指引；
> 若打不开，请从对应官网首页重新查找。

## 一、项目自有文档（保洁系统）

这几份是评测题的**主要依据**，请从你自己的项目仓库/文档系统中整理：

| 文档 | 内容要点 |
| --- | --- |
| 需求说明 | 角色、业务流程、功能列表 |
| 数据库设计 | 表结构、字段含义、索引与约束 |
| 接口文档 | 路径、入参、出参、错误码 |
| 部署文档 | 环境要求、启动方式、配置项 |
| 订单状态机说明 | 状态枚举与流转规则（多跳题常用） |

建议整理成 Markdown，文件名加数字前缀，例如 `01_保洁系统_需求说明.md`。

## 二、框架与中间件官方中文文档

| 主题 | 官方入口 | 建议抓取章节 |
| --- | --- | --- |
| Spring Boot | https://spring.io/projects/spring-boot | 入门、配置、Web、数据访问；中文译文见 https://springdoc.cn/spring-boot/ |
| MyBatis-Plus | https://baomidou.com/ | 快速开始、CRUD 接口、条件构造器、分页插件 |
| Vue 3 | https://cn.vuejs.org/ | 快速上手、响应式基础、组件、组合式 API |
| MySQL | https://dev.mysql.com/doc/ | 数据类型、索引、事务与锁、SQL 语法 |
| MySQL 中文手册（社区译本） | https://www.mysqlzh.com/ | 上述章节的中文对照 |
| Redis | https://redis.io/docs/latest/ | 数据类型、持久化、过期策略、常用命令 |
| Redis 中文文档 | https://redis.com.cn/ | 上述章节的中文对照 |

补充可选来源：

- Spring 官方中文文档站：https://springdoc.cn/
- Vue 官方中文文档站：https://cn.vuejs.org/
- MyBatis-Plus 官方站点：https://baomidou.com/

## 三、抓取与整理建议

1. 只抓**需要的章节**，不要把整站拖下来——语料过大会稀释检索精度，切块也会变慢。
2. 抓成 Markdown 时保留标题层级（`#`/`##`），切块按标题走效果最好。
3. 页面里的导航、页脚、广告请删掉，它们会成为噪声命中。
4. 同一主题只保留一份，避免中文版 + 英文版重复导致检索结果重样。
5. 下载后再次核对：文件能正常打开、编码是 UTF-8、PDF 不是扫描件。

## 四、版权与提交注意

- 第三方官方文档**不要提交到公开仓库**，仅本地离线检索使用；
  `data/raw/` 已被 `.gitignore` 忽略（只放行 `data/raw/README.md`）。
- 引用官方文档做评测时，评测集里只需写文件名（`gold_sources`），无需复制原文。
- 本项目自有文档若含敏感信息，请先脱敏再放入 `data/raw/`。
