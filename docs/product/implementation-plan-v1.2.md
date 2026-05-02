# 企业内部 SQL 问答 Web 应用 Implementation Plan

**版本**：Implementation Plan v1.2  
**状态**：当前工程基线版  
**更新时间**：2026-04-30

**Goal:** 交付一个企业内部可用的本地 Web SQL 问答 MVP，支持 `MySQL / PostgreSQL / Oracle`，采用本地 SQLite 存储、Obsidian 本地知识库、Hermes CLI 生成 SQL、澄清优先、永不自动执行 SQL。

**Architecture:** 前端使用 `Vue + Naive UI` 构建 Web 应用；后端使用本地 `FastAPI` 服务承载数据源连接、Schema 同步、知识库同步、Hermes 编排、SQL 校验、执行与日志；本地 `SQLite` 作为结构化主存储；Obsidian Markdown 作为 Hermes 可读取的知识库载体。

**Tech Stack:** `Vue 3`, `TypeScript`, `Naive UI`, `Vite`, `Vue Router`, `FastAPI`, `SQLModel`, `SQLite`, `Hermes CLI`, `Obsidian Markdown`

---

## 1. 已固定决策

- 前端：`Vue`
- 组件库：`Naive UI`
- 后端：`FastAPI`
- 主存储：`SQLite`
- 知识库载体：`Obsidian Markdown`
- SQL 生成入口：`Hermes CLI`
- SQL 确认方式：`内联确认区`
- SQL 结果行数上限：`500`
- SQL 执行超时：`30 秒`
- 工作台问答准入以当前实现为准：`status = connection_ok` 且 `sync_status = sync_success`
- 首版不开放 SQL 手工编辑执行
- 首版不接入 OpenAI 兼容外部模型
- 首版不使用 embedding

## 2. 阶段 0：文档收口与交付基线

### 2.1 任务目标

- 冻结 PRD / Spec / Implementation Plan 当前口径。
- 明确 Hermes / Obsidian 是当前主链路。
- 明确 SQLite 与 Obsidian 的职责边界。

### 2.2 涉及文档

- `docs/product/prd-v1.2.md`
- `docs/product/spec-v1.2.md`
- `docs/product/implementation-plan-v1.2.md`

### 2.3 验证方式

- 三份文档中不再出现 OpenAI 兼容模型作为首版主链路。
- 三份文档中明确包含 Hermes CLI、Obsidian 知识库、本地运行设置、知识库部分成功、审计日志绑定。

## 3. 阶段 1：项目骨架与基础架构

### 3.1 任务目标

- 建立前后端工程。
- 定义本地数据目录与 SQLite 边界。
- 定义数据源、Schema、知识库任务、审计日志、运行设置模型。

### 3.2 涉及模块 / 文件

- `src/`
- `api/app/`
- `api/app/core/database.py`
- `api/app/core/config.py`
- `api/app/models/*.py`

### 3.3 验证方式

- 前端可构建。
- 后端可启动。
- SQLite 可自动创建表。
- 兼容迁移可补齐新增字段。

## 4. 阶段 2：数据源管理

### 4.1 任务目标

- 定义数据源领域模型。
- 实现 CRUD。
- 实现连接测试。
- 实现数据源管理页。

### 4.2 涉及模块 / 文件

- `api/app/models/datasource.py`
- `api/app/api/routes/datasources.py`
- `api/app/services/datasource_service.py`
- `src/pages/DataSources/`

### 4.3 验证方式

- 能新增、编辑、删除数据源。
- 支持 `MySQL / PostgreSQL / Oracle`。
- 能区分主机不可达、认证失败、数据库不存在、无元数据权限。
- 页面可展示 `draft / connection_failed / connection_ok / sync_failed / ready / stale`。
- 编辑 `db_type / host / port / database / username / password` 后可标记为 `stale`。
- 删除数据源后 Schema 被清理，历史审计日志保留。

## 5. 阶段 3：Schema 同步与备注管理

### 5.1 任务目标

- 实现数据库元数据同步。
- 实现原始备注与本地补充备注双轨模型。
- 实现 Schema / 备注管理页。

### 5.2 涉及模块 / 文件

- `api/app/models/schema.py`
- `api/app/api/routes/schema.py`
- `api/app/services/schema_service.py`
- `src/pages/SchemaManager/`

### 5.3 验证方式

- 能读取表、字段、字段类型、数据库原始备注。
- Schema 同步成功后保留连接可用状态，并提示继续同步到知识库。
- 同步结果为空时不标记为可问答。
- 再同步不会覆盖补充备注。
- 表级和字段级补充备注可编辑。

## 6. 阶段 4：本地运行设置

### 6.1 任务目标

- 实现 Hermes CLI 路径配置。
- 实现 Obsidian 根目录配置。
- 提供本地设置页和可用性测试。

### 6.2 涉及模块 / 文件

- `api/app/models/setting.py`
- `api/app/api/routes/settings.py`
- `api/app/services/setting_service.py`
- `src/pages/Settings/`

### 6.3 验证方式

- 设置保存在 SQLite。
- 未配置时回退到环境默认值。
- 支持 `~` 路径展开。
- Hermes 测试可识别不存在、不可执行、执行失败和可用状态。
- Obsidian 测试可识别不存在、非目录、不可写和可用状态。

## 7. 阶段 5：Obsidian 知识库同步

### 7.1 任务目标

- 基于当前数据源 Schema 和备注生成 Obsidian 知识库。
- 逐表调用 Hermes 生成知识卡片辅助内容。
- 支持 SSE 进度推送。
- 支持部分成功。

### 7.2 涉及模块 / 文件

- `api/app/models/knowledge.py`
- `api/app/services/knowledge_service.py`
- `api/app/api/routes/schema.py`
- `src/pages/SchemaManager/`

### 7.3 验证方式

- 可创建知识库同步任务。
- 可生成数据源 `index.md`。
- 可生成每张表的 Markdown 知识卡片。
- 字段明细始终来自 SQLite Schema。
- Hermes 单表失败不影响后续表。
- 所有表失败时任务为 `failed`。
- 部分表失败时任务为 `partial_success`。
- 任务记录 `completed_tables` 和 `failed_tables`。
- 前端展示同步中、成功、部分成功、失败和过期提示。

## 8. 阶段 6：Hermes 问答与澄清流程

### 8.1 任务目标

- 实现基于当前数据源 Obsidian 知识库的 Hermes 问答。
- 实现 `clarification / sql_candidate` 输出契约。
- 实现多轮澄清上下文。
- 实现工作台。

### 8.2 涉及模块 / 文件

- `api/app/services/hermes_service.py`
- `api/app/services/workbench_service.py`
- `api/app/api/routes/workbench.py`
- `src/pages/Workbench/`

### 8.3 验证方式

- 工作台只使用用户手动选择的数据源。
- 工作台只展示 `connection_ok + sync_success` 的数据源。
- 当前数据源没有知识库时给出明确提示。
- 知识库过期时给出提醒。
- Hermes CLI 不存在、超时、返回非 JSON 时给出明确错误。
- 问题不清楚时先发澄清。
- 澄清后携带上下文继续生成 SQL。
- Hermes 输出结构不合法时被拦截。

## 9. 阶段 7：SQL 校验、内联确认与执行

### 9.1 任务目标

- 实现 SQL 只读校验。
- 实现结果规模与超时保护。
- 实现内联确认区。
- 实现结果表格。

### 9.2 涉及模块 / 文件

- `api/app/services/workbench_service.py`
- `src/pages/Workbench/components/SqlEditor.vue`
- `src/pages/Workbench/components/QueryResult.vue`

### 9.3 验证方式

- 非只读 SQL 一律不可执行。
- 禁止多语句。
- 禁止写操作和有副作用调用。
- 最大返回 500 行。
- 最大执行 30 秒。
- 未确认前绝不执行 SQL。
- 校验失败时按钮禁用并展示原因。
- 正常区分成功有数据、成功无数据、执行失败。

## 10. 阶段 8：本地审计日志

### 10.1 任务目标

- 定义日志模型。
- 实现日志写入与更新服务。
- 实现审计日志页。
- 生成与执行通过 `audit_log_id` 精确绑定。

### 10.2 涉及模块 / 文件

- `api/app/models/audit_log.py`
- `api/app/api/routes/audit.py`
- `api/app/services/workbench_service.py`
- `src/pages/AuditLogs/`

### 10.3 验证方式

- 日志至少覆盖：时间、数据源名称快照、问题、是否澄清、澄清内容、SQL、used notes、是否执行、执行状态、耗时、错误摘要。
- 生成 SQL 后返回 `audit_log_id`。
- 执行 SQL 时回传 `audit_log_id`。
- 执行成功、空结果、失败均更新同一条日志。
- 主流程成功但日志失败时有单独提示。
- 支持按数据源、状态、关键词筛选。
- 删除数据源后历史日志快照仍可读。

## 11. 阶段 9：联调、验收与交付准备

### 11.1 任务目标

- 重建当前 Hermes 路线的测试集。
- 编写端到端验收清单。
- 做跨模块回归。
- 整理本地运行说明。

### 11.2 建议覆盖

- 设置页：Hermes 路径有效/无效、Obsidian 目录有效/无效。
- 数据源：连接成功/失败、编辑 db_type 后 stale。
- Schema：同步成功/空结果/失败。
- 备注：表备注和字段备注保存。
- 知识库：全部成功、部分成功、全部失败、目录不可写、Hermes 超时。
- 问答：无知识库、知识库过期、澄清、SQL 候选、Hermes 非 JSON。
- SQL：校验成功、校验失败、执行成功、空结果、执行失败。
- 审计：生成与执行精确绑定。

### 11.3 验证命令

- `npm run build`
- `PYTHONPATH=api .venv/bin/python -m compileall -q api/app`
- 后续补充新的前后端自动化测试命令。

## 12. Google Docs / Google Drive 发布计划

本地先整理三份当前基线文档，再同步到 Google Drive。  
需要发布的文档包括：

- PRD
- Spec
- Implementation Plan
