# 企业内部 SQL 问答 Web 应用 Implementation Plan

**版本**：Implementation Plan v1.2  
**状态**：当前工程基线版  
**更新时间**：2026-05-04

**Goal:** 交付一个企业内部可用的本地 Web SQL 问答 MVP，支持本地登录鉴权、`MySQL / PostgreSQL / Oracle`，采用本地 SQLite 存储和主检索、Obsidian 本地知识库补充业务说明、Hermes CLI 生成 SQL、澄清优先、永不自动执行 SQL。

**Architecture:** 前端使用 `Vue + Naive UI` 构建 Web 应用；后端使用本地 `FastAPI` 服务承载登录鉴权、数据源连接、Schema 同步、知识库同步、Schema 检索、Hermes 编排、SQL 校验、执行与日志；本地 `SQLite` 作为结构化主存储和问答主检索层；Obsidian Markdown 作为人类可读的知识库与 LLM 补充上下文。

**Tech Stack:** `Vue 3`, `TypeScript`, `Naive UI`, `Vite`, `Vue Router`, `FastAPI`, `SQLModel`, `SQLite`, `cryptography`, `hmac/hashlib`, `WebCrypto`, `ReadableStream`, `Hermes CLI`, `Obsidian Markdown`

---

## 1. 已固定决策

- 前端：`Vue`
- 组件库：`Naive UI`
- 后端：`FastAPI`
- 主存储：`SQLite`
- 问答主检索：`SQLite Schema Context`
- 知识库载体：`Obsidian Markdown`
- SQL 生成入口：`Hermes CLI`
- SQL 确认方式：`内联确认区`
- SQL 结果行数上限：`500`
- SQL 执行超时：`30 秒`
- 初始管理员账号：`admin / 888888`
- 登录密码传输方式：`RSA-OAEP + SHA-256`
- 前端 Token 保存方式：`localStorage`
- 业务请求鉴权方式：`Authorization: Bearer <token>`
- 登录成功默认页：`数据源配置页`
- 流式请求实现：`fetch + ReadableStream`，不得退回前端轮询
- Token 有效期：`480 分钟`
- Token 格式：标准库 HMAC-SHA256 签名，不额外引入 JWT 依赖
- RSA 密钥路径：`{DATA_DIR}/auth/rsa_private.pem`、`{DATA_DIR}/auth/rsa_public.pem`
- 工作台问答准入以当前实现为准：`status = connection_ok` 且 `sync_status = sync_success`
- 首版不开放 SQL 手工编辑执行
- 首版不接入 OpenAI 兼容外部模型
- 首版不使用 embedding

## 2. 阶段 0：文档收口与交付基线

### 2.1 任务目标

- 冻结 PRD / Spec / Implementation Plan 当前口径。
- 明确 SQLite-first Schema 检索是当前问答主链路。
- 明确 SQLite、Obsidian、Hermes 和 SQL 校验器的职责边界。

### 2.2 涉及文档

- `docs/product/prd-v1.2.md`
- `docs/product/spec-v1.2.md`
- `docs/product/implementation-plan-v1.2.md`

### 2.3 验证方式

- 三份文档中不再出现 OpenAI 兼容模型作为首版主链路。
- 三份文档中明确包含 SQLite Schema 检索、Hermes CLI、Obsidian 知识库、本地运行设置、知识库部分成功、审计日志绑定。

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

## 4. 阶段 1.5：本地登录与鉴权

### 4.1 任务目标

- 建立本地用户表和登录日志表。
- 初始化管理员账号 `admin / 888888`。
- 密码使用 `PBKDF2-HMAC-SHA256` 哈希保存，数据库不保存明文密码。
- 实现 RSA 公钥获取、密码解密、密码哈希校验和 Token 签发。
- 保护业务接口，要求携带 `Authorization: Bearer <token>`。
- 实现前端登录页、Token 存储、路由守卫和请求鉴权。
- 将流式请求从原生 `EventSource` 迁移到 `fetch + ReadableStream`，保持长连接推送且支持请求头鉴权。

### 4.2 涉及模块 / 文件

- `api/app/models/user.py`
- `api/app/models/login_log.py`
- `api/app/core/security.py`
- `api/app/services/auth_service.py`
- `api/app/api/routes/auth.py`
- `api/app/api/deps.py`
- `src/pages/Login/`
- `src/services/auth.ts`
- `src/services/request.ts`
- `src/router.ts`
- `src/App.vue`
- `src/components/layout/AppSidebar.vue`
- `src/pages/Workbench/index.vue`
- `src/pages/SchemaManager/index.vue`
- `api/tests/test_auth_service.py`
- `api/tests/test_auth_routes.py`
- `tests/auth.spec.ts`
- `tests/stream-sse.spec.ts`

### 4.3 验证方式

- 首次启动自动创建 `admin / 888888`。
- 仅首次不存在 `admin` 时创建默认账号；已存在 `admin` 时保留原密码。
- 登录密码使用 RSA 加密传输。
- 数据库不保存明文密码，密码哈希不等于明文。
- 相同密码不同 Salt 生成不同 Hash。
- 登录成功返回 Token 和用户信息。
- 登录成功默认进入数据源配置页。
- 错误密码、账号不存在、禁用账号不可登录。
- 无 Token、无效 Token、过期 Token 访问业务接口返回 `401`。
- 无 Token 访问业务页面回到登录页。
- `/auth/public-key` 和 `/auth/login` 无需 Token。
- 普通请求自动携带 Token。
- 工作台问答和知识库同步流式请求自动携带 Token，且不使用前端轮询。
- `streamSse` 可以解析 `status / result / error` 等 SSE 事件。
- `AbortController.abort()` 可以中断流式读取。
- 登录成功和失败均写入登录日志。

### 4.4 后端接口与鉴权

新增认证接口：

- `GET /api/v1/auth/public-key`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

业务路由统一增加当前用户依赖：

- `datasources`
- `schema`
- `workbench`
- `audit`
- `settings`

放行路由：

- `GET /api/v1/health`
- `GET /api/v1/auth/public-key`
- `POST /api/v1/auth/login`

### 4.5 前端登录与请求改造

登录页：

- 参考 `stitch_sql_ux_v1/naive_ui_style_refined_4/code.html`。
- 展示 `FastGenerate SQL`、账号输入、密码输入、密码可见切换、登录按钮、错误提示和加载状态。
- 账号为空提示 `请输入账号`。
- 密码为空提示 `请输入密码`。

认证工具：

- 新增 `src/services/auth.ts`。
- 保存、读取、清除 Token。
- 保存、读取当前用户。
- 获取 RSA 公钥并用 WebCrypto 加密密码。
- 调用登录接口和 `/auth/me`。
- localStorage key 为 `fg_sql_token`、`fg_sql_user`。

请求工具：

- `src/services/request.ts` 自动注入 `Authorization`。
- 普通请求收到 `401` 后清除登录态并跳转登录页。
- 新增 `streamSse(path, handlers, options)`，使用 `fetch`、`ReadableStream`、`TextDecoder` 增量解析 SSE。

路由和布局：

- 新增 `/login`。
- 业务路由添加 `meta.requiresAuth`。
- 无 Token 访问业务页跳转 `/login?redirect=<target>`。
- 已登录访问 `/login` 跳转工作台。
- `/login` 不显示业务侧边栏，其他页面保留现有业务布局。
- 侧边栏展示当前用户，并提供退出登录。

流式迁移：

- 工作台问答从 `EventSource` 切换为 `streamSse`，保留 `status / note_used / hermes_trace / result / error` 事件；`status.phase = retrieving_schema` 表示后端正在检索 SQLite Schema Context。
- 知识库同步订阅从 `EventSource` 切换为 `streamSse`，保留“启动任务”和“订阅任务”分离。
- 终态或组件卸载时调用 `AbortController.abort()`。

## 5. 阶段 2：数据源管理

### 5.1 任务目标

- 定义数据源领域模型。
- 实现 CRUD。
- 实现连接测试。
- 实现数据源管理页。

### 5.2 涉及模块 / 文件

- `api/app/models/datasource.py`
- `api/app/api/routes/datasources.py`
- `api/app/services/datasource_service.py`
- `src/pages/DataSources/`

### 5.3 验证方式

- 能新增、编辑、删除数据源。
- 支持 `MySQL / PostgreSQL / Oracle`。
- 普通用户名密码连接模式下，数据库密码以本地 AES-GCM 密文保存到 SQLite，服务启动时迁移旧明文密码。
- 能区分主机不可达、认证失败、数据库不存在、无元数据权限。
- 页面可展示 `draft / connection_failed / connection_ok / sync_failed / stale`。
- 编辑 `db_type / host / port / database / username / password` 后可标记为 `stale`。
- 删除数据源后 Schema 被清理，历史审计日志保留。

## 6. 阶段 3：Schema 同步与备注管理

### 6.1 任务目标

- 实现数据库元数据同步。
- 实现原始备注与本地补充备注双轨模型。
- 实现 Schema / 备注管理页。

### 6.2 涉及模块 / 文件

- `api/app/models/schema.py`
- `api/app/api/routes/schema.py`
- `api/app/services/schema_service.py`
- `src/pages/SchemaManager/`

### 6.3 验证方式

- 能读取表、字段、字段类型、数据库原始备注。
- Schema 同步成功后保留连接可用状态，并提示继续同步到知识库。
- 同步结果为空时不标记为可问答。
- 再同步不会覆盖补充备注。
- 再同步会清理数据库中已删除的表和字段，并删除对应已删除表的旧 Obsidian Markdown 文件。
- 数据源已完成知识库同步后再次同步 Schema，必须将 `sync_status` 改回非成功态，要求用户重新同步知识库。
- 表级和字段级补充备注可编辑。

## 7. 阶段 4：本地运行设置

### 7.1 任务目标

- 实现 Hermes CLI 路径配置。
- 实现 Obsidian 根目录配置。
- 提供本地设置页和可用性测试。

### 7.2 涉及模块 / 文件

- `api/app/models/setting.py`
- `api/app/api/routes/settings.py`
- `api/app/services/setting_service.py`
- `src/pages/Settings/`

### 7.3 验证方式

- 设置保存在 SQLite。
- 未配置时回退到环境默认值。
- 支持 `~` 路径展开。
- Hermes 测试可识别不存在、不可执行、执行失败和可用状态。
- Obsidian 测试可识别不存在、非目录、不可写和可用状态。

## 8. 阶段 5：Obsidian 知识库同步

### 8.1 任务目标

- 基于当前数据源 Schema 和备注生成 Obsidian 知识库。
- 逐表调用 Hermes 生成知识卡片辅助内容。
- 支持 SSE 进度推送。
- 支持部分成功。
- 后端创建任务后快速返回，后台执行文件生成，任务不依赖 SSE 连接存活。
- 输出数据源总览页和单表详情页，重复同步同一数据源时覆盖同一目录。

### 8.2 涉及模块 / 文件

- `api/app/models/knowledge.py`
- `api/app/services/knowledge_service.py`
- `api/app/api/routes/schema.py`
- `src/pages/SchemaManager/`
- `src/pages/SchemaManager/components/SchemaEditor.vue`
- `api/tests/test_knowledge_notifier.py`
- `tests/schema-knowledge-sync.spec.ts`

### 8.3 验证方式

- 可创建知识库同步任务。
- 数据源无同步表时正确拒绝。
- 可生成数据源 `index.md`。
- 可生成每张表的 Markdown 知识卡片。
- 文件名会做安全清洗，非法路径字符不会进入文件名。
- 字段明细始终来自 SQLite Schema。
- Hermes 生成内容只进入用途说明、核心字段解读、常见关联关系和注意事项。
- Hermes 单表失败不影响后续表。
- 所有表失败时任务为 `failed`。
- 部分表失败时任务为 `partial_success`。
- 任务记录 `completed_tables` 和 `failed_tables`。
- Obsidian 根目录不存在、不可写或文件写入失败时，任务记录可读错误信息。
- 失败时保留已生成的部分文件，重试时覆盖同一数据源目录。
- 前端展示同步中、成功、部分成功、失败和过期提示。
- 前端展示 `同步到知识库` 按钮，点击后发起启动请求并订阅 SSE。
- 刷新页面后可以重新订阅进行中的任务。

### 8.4 接口清单

- `POST /api/v1/schema/knowledge/sync/{datasource_id}`：启动知识库同步任务。
- `GET /api/v1/schema/knowledge/tasks/{task_id}`：查询任务状态。
- `GET /api/v1/schema/knowledge/tasks/{task_id}/events`：SSE 订阅任务进度。
- `GET /api/v1/schema/knowledge/status/{datasource_id}`：查询数据源当前知识库任务状态，用于刷新后恢复。

### 8.5 实施顺序

1. 新增知识库任务模型及初始化逻辑。
2. 新增知识库同步接口。
3. 实现从 SQLite 读取 Schema 与备注的服务逻辑。
4. 实现 Markdown 渲染和文件写入。
5. 接入 Hermes 逐表增强生成。
6. 打通后台执行和任务状态更新。
7. 增加前端按钮与进度展示。
8. 补充后端和前端测试。

## 9. 阶段 6：Hermes 问答与澄清流程

### 9.1 任务目标

- 实现基于当前数据源 SQLite Schema Context 的主检索链路。
- 实现按相关表读取 Obsidian 表卡片作为补充上下文。
- 实现由 Hermes 在受控上下文内完成澄清、关系补全和 SQL 生成的问答链路。
- 实现 `clarification / sql_candidate` 输出契约。
- 实现多轮澄清上下文。
- 实现工作台。

### 9.2 涉及模块 / 文件

- `api/app/services/hermes_service.py`
- `api/app/services/workbench_service.py`
- `api/app/api/routes/workbench.py`
- `src/pages/Workbench/`

### 9.3 验证方式

- 工作台可以默认选中第一个 `connection_ok + sync_success` 的数据源，但不得根据问题内容自动切换数据源。
- 工作台只展示 `connection_ok + sync_success` 的数据源。
- 当前数据源没有知识库时给出明确提示。
- 知识库过期时给出提醒。
- 提问后先发送 `retrieving_schema` 状态，并从 SQLite 检索相关 Schema Context。
- 只读取相关表对应的 Obsidian Markdown 片段，不直接全量扫描 Obsidian。
- Hermes CLI 不存在、超时、返回非 JSON 时给出明确错误。
- 问题不清楚时先发澄清。
- 澄清后携带最近对话上下文重新检索 Schema，避免用户短回复导致上下文丢失。
- Hermes 输出结构不合法时被拦截。

## 10. 阶段 7：SQL 校验、内联确认与执行

### 10.1 任务目标

- 实现 SQL 只读校验。
- 实现结果规模与超时保护。
- 实现内联确认区。
- 实现结果表格。

### 10.2 涉及模块 / 文件

- `api/app/services/workbench_service.py`
- `src/pages/Workbench/components/SqlEditor.vue`
- `src/pages/Workbench/components/QueryResult.vue`

### 10.3 验证方式

- 非只读 SQL 一律不可执行。
- 禁止多语句。
- 禁止写操作和有副作用调用。
- SQL 引用不存在的限定表字段时必须阻断。
- 无法确认的未限定字段候选降级为 warning。
- 最大返回 500 行。
- 最大执行 30 秒。
- 未确认前绝不执行 SQL。
- 校验失败时按钮禁用并展示原因。
- 正常区分成功有数据、成功无数据、执行失败。

## 11. 阶段 8：本地审计日志

### 11.1 任务目标

- 定义日志模型。
- 实现日志写入与更新服务。
- 实现审计日志页。
- 生成与执行通过 `audit_log_id` 精确绑定。

### 11.2 涉及模块 / 文件

- `api/app/models/audit_log.py`
- `api/app/api/routes/audit.py`
- `api/app/services/workbench_service.py`
- `src/pages/AuditLogs/`

### 11.3 验证方式

- 日志至少覆盖：时间、数据源名称快照、问题、是否澄清、澄清内容、SQL、used notes、是否执行、执行状态、耗时、错误摘要。
- 生成 SQL 后返回 `audit_log_id`。
- 执行 SQL 时回传 `audit_log_id`。
- 执行成功、空结果、失败均更新同一条日志。
- 主流程成功但日志失败时有单独提示。
- 支持按数据源、状态、关键词筛选。
- 删除数据源后历史日志快照仍可读。

## 12. 阶段 9：联调、验收与交付准备

### 12.1 任务目标

- 重建当前 SQLite-first Schema 检索和 Hermes 编排路线的测试集。
- 编写端到端验收清单。
- 做跨模块回归。
- 整理本地运行说明。

### 12.2 建议覆盖

- 登录：初始账号、RSA 加密、登录成功、登录失败、登录日志。
- 登录细节：密码哈希、Salt 随机性、禁用账号、账号不存在、`/auth/me`。
- 鉴权：无 Token、无效 Token、过期 Token、业务路由守卫、业务接口保护、`401` 清理登录态。
- 流式：工作台问答和知识库同步使用 `fetch + ReadableStream` 携带 Token，不使用前端轮询，支持事件解析和主动中断。
- 设置页：Hermes 路径有效/无效、Obsidian 目录有效/无效。
- 数据源：连接成功/失败、编辑 db_type 后 stale。
- Schema：同步成功/空结果/失败。
- 备注：表备注和字段备注保存。
- 知识库：任务创建、无同步表拒绝、Markdown 渲染、文件名清洗、进度更新、全部成功、部分成功、全部失败、目录不存在、目录不可写、Hermes 超时、Hermes 非法输出、文件写入失败、刷新后重新订阅。
- 问答：无知识库、知识库过期、SQLite Schema 检索、相关 Obsidian notes、澄清、澄清后上下文保留、SQL 候选、Hermes 非 JSON。
- SQL：校验成功、校验失败、执行成功、空结果、执行失败。
- 审计：生成与执行精确绑定。

### 12.3 验证命令

- `npm run build`
- `npm test`
- `cd api && ./venv/bin/python -m pytest tests -q`
- `cd api && ./venv/bin/python -m compileall -q app`
- 后续补充新的前后端自动化测试命令。

## 13. 风险与决策

- `localStorage` 容易受到 XSS 影响。当前项目是本地内部工具，首版接受该实现以降低复杂度；后续如需提高安全性，可以改为后端设置 HttpOnly Cookie。
- RSA 只保护登录密码字段，不能替代 HTTPS。如果部署到网络环境，仍应启用 HTTPS。
- 原生 `EventSource` 不能设置自定义请求头，无法满足“前端所有请求必须携带 Token”。改为 `fetch + ReadableStream` 后仍是长连接流式接收，不是轮询。
- 当前项目使用 `create_all` 加手工 `ALTER TABLE` 的轻量迁移方式。新增表可由 `create_all` 创建；如后续用户表字段调整，需要在兼容迁移逻辑中补齐。
- 知识库同步使用后端后台任务适合当前本地单用户场景；如果未来进入多进程或多人使用，需要演进为进程内任务队列或独立 worker。
- 当表命名不清晰时，Hermes 可能会对关联关系做出不准确推断；Prompt 必须要求推测性内容显式标记不确定性，后端 SQL Schema 校验必须阻断明确不存在的限定字段。

## 14. Google Docs / Google Drive 发布计划

本地先整理三份当前基线文档，再同步到 Google Drive。  
需要发布的文档包括：

- PRD
- Spec
- Implementation Plan
