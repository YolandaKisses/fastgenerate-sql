# Obsidian 知识库同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为当前项目增加“同步到知识库”能力，通过 Python 后端调用 Hermes 生成数据源总览页与单表 Markdown，并把结果写入本地运行设置中配置的 Obsidian 目录。

**Architecture:** 前端在 Schema 管理页新增触发按钮和 SSE 进度展示；后端新增知识库同步任务模型、启动接口、SSE 订阅接口和服务，复用 SQLite 中已有的 Schema 与补充备注作为输入；Hermes 仅负责生成增强说明，结构化字段明细由本地数据直接渲染到 Markdown。

**Tech Stack:** Vue 3、Naive UI、FastAPI、SQLModel、SQLite、unittest、Vitest

---

### Task 1: 后端任务模型与服务测试

**Files:**
- Create: `api/app/models/knowledge.py`
- Modify: `api/tests/test_services.py`

- [ ] Step 1: 编写失败测试，覆盖知识库任务创建、Markdown 渲染和缺少同步表时的错误返回。
- [ ] Step 2: 运行 `cd api && python -m unittest tests.test_services.ServiceTests.test_create_knowledge_sync_task tests.test_services.ServiceTests.test_generate_table_markdown tests.test_services.ServiceTests.test_create_knowledge_sync_task_requires_tables`
- [ ] Step 3: 最小实现任务模型和服务接口占位。
- [ ] Step 4: 重新运行同一组测试直到通过。

### Task 2: 后端知识库同步实现

**Files:**
- Create: `api/app/services/knowledge_service.py`
- Modify: `api/app/core/config.py`
- Modify: `api/app/models/__init__.py`

- [ ] Step 1: 补充失败测试，覆盖任务状态更新、文件名清洗和任务执行完成状态。
- [ ] Step 2: 运行对应 unittest，确认失败原因正确。
- [ ] Step 3: 实现知识库任务创建、Hermes 调用、Markdown 渲染、Obsidian 可配置目录写文件和状态更新。
- [ ] Step 4: 重新运行对应 unittest，确认通过。

### Task 3: 后端接口接入

**Files:**
- Modify: `api/app/api/routes/schema.py`
- Modify: `api/app/main.py`

- [ ] Step 1: 编写失败测试，覆盖任务状态查询和接口入参校验。
- [ ] Step 2: 运行后端测试确认失败。
- [ ] Step 3: 实现 `POST /api/v1/schema/knowledge/sync/{datasource_id}` 启动后台任务、`GET /api/v1/schema/knowledge/tasks/{task_id}` 查询状态、`GET /api/v1/schema/knowledge/tasks/{task_id}/events` 通过 SSE 订阅进度；任务执行不得依赖 SSE 连接存活。
- [ ] Step 4: 重新运行相关 unittest，确认通过。

### Task 4: 前端交互与状态展示

**Files:**
- Modify: `src/pages/SchemaManager/index.vue`
- Modify: `src/pages/SchemaManager/components/SchemaEditor.vue`
- Create: `tests/schema-knowledge-sync.spec.ts`

- [ ] Step 1: 编写失败测试，覆盖“同步到知识库”按钮展示、点击后发起启动请求、SSE 订阅任务状态和展示进度。
- [ ] Step 2: 运行 `npm test -- tests/schema-knowledge-sync.spec.ts`，确认失败。
- [ ] Step 3: 最小实现前端按钮、禁用态、任务状态展示和 SSE 订阅逻辑；刷新页面后应重新订阅进行中的任务。
- [ ] Step 4: 重新运行前端测试，确认通过。

### Task 5: 全量验证

**Files:**
- Modify: `api/tests/test_services.py`
- Modify: `tests/schema-knowledge-sync.spec.ts`

- [ ] Step 1: 运行后端知识库同步相关 unittest。
- [ ] Step 2: 运行前端 Vitest。
- [ ] Step 3: 运行构建 `npm run build`。
- [ ] Step 4: 记录未覆盖风险，仅在验证结果真实通过后再宣告完成。
