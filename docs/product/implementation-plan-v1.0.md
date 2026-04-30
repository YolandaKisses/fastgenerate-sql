# 企业内部 SQL 问答 Web 应用 Implementation Plan

**版本**：Implementation Plan v1.0  
**状态**：已确认发布版

**Goal:** 从 0 到 1 交付一个企业内部可用的 Web SQL 问答 MVP，支持 `MySQL / PostgreSQL / Oracle`，采用本地 SQLite 存储、关键词/规则 Schema 召回、OpenAI 兼容模型、澄清优先、永不自动执行 SQL。

**Architecture:** 前端使用 `Vue + Naive UI` 构建 Web 应用，后端使用本地 `FastAPI` 服务承载数据源连接、Schema 同步、召回、LLM 编排、SQL 校验、执行与日志，本地 `SQLite` 作为唯一主存储。

**Tech Stack:** `Vue 3`, `TypeScript`, `Naive UI`, `Vite`, `Pinia`, `Vue Router`, `FastAPI`, `SQLAlchemy/SQLModel`, `SQLite`

---

## 1. 已固定决策

- 前端：`Vue`
- 组件库：`Naive UI`
- 技术栈：`Vue 3 + TypeScript + Naive UI + FastAPI + SQLite`
- SQL 确认方式：`内联确认区`
- 不复用任何现有 Stitch 项目
- SQL 结果行数上限：`500`
- SQL 执行超时：`30 秒`
- 只要通过连接测试即可问答
- 首版不开放 SQL 手工编辑执行

## 2. 阶段 0：文档收口与交付基线

### 2.1 任务目标

- 冻结中文 PRD / spec / implementation plan
- 补运行时约束清单

### 2.2 涉及文档

- `docs/product/prd-v1.1.md`
- `docs/product/spec-v1.0.md`
- `docs/product/implementation-plan-v1.0.md`
- `docs/product/runtime-guardrails.md`

### 2.3 验证方式

- 三份文档中不出现互相矛盾的口径
- 明确包含“不使用 embedding、永不自动执行 SQL、连接测试通过即可问答、结果上限 500 行、执行超时 30 秒”

## 3. 阶段 1：设计准备与视觉方向

### 3.1 任务目标

- 生成页面清单与设计输入
- 先做 GPT Image 风格探索
- 再转成 Stitch prompt 与设计稿

### 3.2 页面清单

- 问答主页面
- 数据源管理页
- Schema / 备注管理页
- 模型配置页
- 审计日志页

### 3.3 设计顺序

1. GPT Image：问答主页面、审计日志页
2. Stitch：数据源管理页、Schema / 备注管理页、模型配置页、审计日志页、问答主页面

### 3.4 涉及文档

- `docs/design/page-inventory.md`
- `docs/design/stitch-prompts/chat-workbench.md`
- `docs/design/stitch-prompts/audit-log.md`
- `docs/design/stitch-prompts/datasource-management.md`
- `docs/design/stitch-prompts/schema-remarks.md`
- `docs/design/stitch-prompts/model-config.md`
- `docs/design/design-system.md`
- `docs/design/page-contracts/*.md`

### 3.5 验证方式

- 每个页面都有目标、模块、状态、关键交互说明
- GPT Image 方向符合“企业级、克制、工具型、高信息密度、可信”
- Stitch 设计稿能直接映射回 spec 页面定义

## 4. 阶段 2：项目骨架与基础架构

### 4.1 任务目标

- 初始化项目目录
- 定义本地数据目录与 SQLite 边界
- 定义统一状态机

### 4.2 涉及模块 / 文件

- `apps/web/`
- `apps/api/`
- `docs/architecture/monorepo-structure.md`
- `docs/architecture/local-storage.md`
- `docs/architecture/state-machine.md`

### 4.3 验证方式

- 目录职责清晰
- 存储边界明确
- 状态机可覆盖数据源、同步、问答、执行、日志

## 5. 阶段 3：数据源管理

### 5.1 任务目标

- 定义数据源领域模型
- 实现 CRUD
- 实现连接测试
- 实现数据源管理页

### 5.2 涉及模块 / 文件

- `apps/api/app/modules/datasources/`
- `apps/api/app/models/datasource.py`
- `apps/api/app/schemas/datasource.py`
- `apps/api/app/modules/datasources/routes.py`
- `apps/api/app/modules/datasources/service.py`
- `apps/api/app/modules/datasources/connectivity.py`
- `apps/web/src/features/datasources/`
- `apps/web/src/pages/datasources/`
- `apps/web/src/components/datasources/`

### 5.3 验证方式

- 能新增、编辑、删除数据源
- 能区分主机不可达、认证失败、数据库不存在、无元数据权限
- 页面可展示 `draft / connection_failed / connection_ok / sync_failed / ready / stale`

## 6. 阶段 4：Schema 同步与备注管理

### 6.1 任务目标

- 实现 MySQL / PostgreSQL / Oracle 元数据适配层
- 实现同步服务与本地入库
- 实现原始备注与本地补充备注双轨模型
- 实现 Schema / 备注管理页

### 6.2 涉及模块 / 文件

- `apps/api/app/modules/schema_sync/adapters/mysql.py`
- `apps/api/app/modules/schema_sync/adapters/postgresql.py`
- `apps/api/app/modules/schema_sync/adapters/oracle.py`
- `apps/api/app/modules/schema_sync/service.py`
- `apps/api/app/models/schema_table.py`
- `apps/api/app/models/schema_field.py`
- `apps/api/app/modules/remarks/`
- `apps/api/app/models/remark.py`
- `apps/web/src/pages/schema/`
- `apps/web/src/components/schema/`

### 6.3 验证方式

- 能读取表、字段、字段类型、数据库原始备注
- 同步成功后数据源进入 `ready`
- 通过连接测试的数据源即可问答，同步结果用于增强召回质量
- 再同步不会覆盖补充备注
- 补充备注可参与后续召回

## 7. 阶段 5：模型配置与运行时约束

### 7.1 任务目标

- 实现 OpenAI 兼容模型配置
- 定义 LLM 输出契约
- 实现三层约束机制

### 7.2 涉及模块 / 文件

- `apps/api/app/modules/model_config/`
- `apps/web/src/pages/model-config/`
- `apps/api/app/modules/llm/contracts.py`
- `apps/api/app/modules/qa_guardrails/`
- `apps/api/app/modules/llm/prompts/`

### 7.3 验证方式

- 能配置 Base URL、API Key、Model Name、timeout、temperature
- LLM 输出只允许 `clarification` 或 `sql_candidate`
- 高歧义场景先澄清
- 返回结构不合法时能被拦截

## 8. 阶段 6：问答与澄清流程

### 8.1 任务目标

- 实现基于关键词/规则的 Schema 召回
- 实现澄清状态机
- 实现问答主页面

### 8.2 涉及模块 / 文件

- `apps/api/app/modules/retrieval/`
- `apps/api/app/modules/chat_flow/`
- `apps/web/src/pages/chat/`
- `apps/web/src/components/chat/`

### 8.3 验证方式

- 只在当前数据源内召回
- 问题不清楚时先发澄清
- 澄清后继续收敛
- 多次澄清仍不清楚时终止生成 SQL
- 单页完成“选数据源 -> 提问 -> 澄清 -> 展示 SQL -> 内联确认 -> 执行 -> 看结果”

## 9. 阶段 7：SQL 校验、内联确认与执行

### 9.1 任务目标

- 实现 SQL 只读校验
- 实现结果规模与超时保护
- 实现内联确认区
- 实现结果表格

### 9.2 涉及模块 / 文件

- `apps/api/app/modules/sql_validation/`
- `apps/api/app/modules/sql_execution/limits.py`
- `apps/api/app/modules/sql_execution/`
- `apps/web/src/components/chat/sql-review-panel.*`
- `apps/web/src/components/results/`

### 9.3 验证方式

- 非只读 SQL 一律不可执行
- 不限制多表查询结构，只限制：
  - 只读性
  - 最大返回 500 行
  - 最大执行 30 秒
  - 禁止多语句
- 未确认前绝不执行 SQL
- 正常区分成功有数据、成功无数据、执行失败

## 10. 阶段 8：本地审计日志

### 10.1 任务目标

- 定义日志模型
- 实现日志写入服务
- 实现审计日志页

### 10.2 涉及模块 / 文件

- `apps/api/app/models/audit_log.py`
- `apps/api/app/modules/audit/`
- `apps/api/app/modules/audit/service.py`
- `apps/web/src/pages/audit/`
- `apps/web/src/components/audit/`

### 10.3 验证方式

- 日志至少覆盖：时间、数据源名称快照、问题、是否澄清、澄清内容、SQL、是否执行、执行状态、耗时、错误摘要
- 主流程成功但日志失败时有单独提示
- 支持按数据源、状态、关键词筛选
- 删除数据源后历史日志快照仍可读

## 11. 阶段 9：联调、验收与交付准备

### 11.1 任务目标

- 编写端到端验收清单
- 做跨模块回归
- 整理开发与发布说明

### 11.2 涉及文档

- `docs/qa/e2e-checklist.md`
- `docs/release/local-setup.md`
- `docs/release/known-limitations.md`

### 11.3 验证方式

- 覆盖 MySQL / PostgreSQL / Oracle
- 覆盖连接成功/失败、同步成功/失败、澄清成功/失败、生成 SQL 成功/失败、校验失败、执行成功/空结果/失败
- 验证改数据源后建议重新同步、改补充备注会影响召回、模型配置无效时问答被拦截、未确认前不执行 SQL

## 12. 设计稿生成链路

### 12.1 GPT Image 的使用时机

- 先做：问答主页面、审计日志页
- 目标：定视觉方向、桌面工具氛围、信息层次

### 12.2 Stitch 的使用时机

- GPT Image 风格确定后，再生成：
  - 数据源管理页
  - Schema / 备注管理页
  - 模型配置页
  - 审计日志页
  - 问答主页面

### 12.3 GPT Image 产物如何转成 Stitch 输入

- 提取页面布局、色彩、排版、状态表达、模块层次
- 写成结构化中文 Stitch prompt

### 12.4 Stitch 设计稿如何作为开发依据

- 每页必须配：
  - 页面截图
  - 模块说明
  - 状态说明
  - 交互说明

## 13. Google Docs / Google Drive 发布计划

本地先整理三份中文发布版文档，再统一写入 Google Docs / Google Drive。  
需要发布的文档包括：

- PRD
- Spec
- Implementation Plan
