# FastGenerate SQL 项目架构与设计 Review

## 1. 项目整体架构设计

FastGenerate SQL 是一个由 Vue 3 + Naive UI (前端) 和 FastAPI + SQLModel (后端) 构成的本地轻量级 SQL 生成与执行工作台。

- **存储方案**：本地 SQLite (`fastgenerate.db`) 持久化元数据和配置，采用 Obsidian Vault 作为业务语义和口径的外部知识库。
- **核心定位**：提供受控、安全的 "Text-to-SQL" 生成体验，支持多数据源 (MySQL, PostgreSQL, Oracle)。
- **安全设计**：强制拦截 DML (INSERT/UPDATE/DELETE 等) 和 DDL 语句，只允许只读 (SELECT/WITH) 操作；数据库密码在本地使用 AES-GCM 加密存储。

## 2. 核心工作流程 (SQL 生成与执行)

整个流程分为两层：精确的元数据检索和 LLM 逻辑推理。

1. **用户输入问题**：前端将用户问题和压缩后的上下文历史发送给后端 (`/workbench/ask_stream` 接口)。
2. **SQLite 本地检索 (Schema 召回)**：
   - 使用 `workbench_service.py` 中的 `retrieve_relevant_schema`，根据用户的分词 (结合预定义的语义别名字典 `SEMANTIC_TOKEN_ALIASES`)，在 SQLite 本地缓存的表中检索出 Top N 候选表 (基于表名、注释和字段名的评分匹配机制)。
3. **知识库补充 (Obsidian Notes RAG)**：
   - 根据命中的候选表，精准读取 Obsidian 中对应的 Markdown 笔记，以补充具体的业务语义和统计口径。
4. **LLM 交互 (Hermes Agent)**：
   - 构建带有强规则的 Prompt，包含召回的 Schema 结构、Obsidian Notes 业务口径和用户当前及历史问题。
   - 调用外部 `hermes` CLI 处理对话，生成标准的 JSON 返回（`sql_candidate` 或 `clarification`）。
5. **本地防幻觉与语义校验**：
   - 解析 LLM 返回的 SQL，执行轻量级的正则 AST 校验 (`validate_sql_against_schema`)，严格拦截对未在上下文中提供的表或字段的使用。
   - 包含特定的业务拦截逻辑：例如当外卖查询缺乏明确语义时，强制回退进入澄清模式 (`guard_sql_candidate_against_missing_semantics`)。
6. **SQL 确认与执行**：前端流式渐进渲染生成的 SQL，用户确认后通过只读参数执行语句，最后记录并沉淀至审计日志。

## 3. 着重强调：对话机制设计 (Conversation Mechanism)

本项目的核心亮点在于其**受控的多轮澄清对话机制**。这与普通的 "一问一答并强行生成可能错误的 SQL" 的 AI 有显著区别：

### 3.1 状态管理与上下文维持

- **前端状态管理 (`workbenchState.ts`)**：工作台支持多窗口 (Tabs)，每个窗口维护独立隔离的对话历史 (`messageHistory`)。历史记录通过 `compactMessageHistoryForStorage` 压缩，控制 Prompt 长度上限。
- **底层会话接力 (`hermes_service.py`)**：后端调用 `hermes chat` CLI，通过匹配和传递 `session_id` 维持底层的 LLM 会话状态。这保证了即使 HTTP 层面只是无状态的 SSE 请求，LLM 也能深度理解多轮上下文连续性。

### 3.2 歧义阻断与澄清 (Clarification)

- **强制选择题**：严禁 LLM 盲目猜测表或字段。Prompt 中明确要求，如果问题模糊、缺少过滤条件或无法确定统计口径，LLM 必须返回 `{"type": "clarification"}` 格式，并给出最多 4 个具体的 A/B/C/D 候选项。
- **自动自我纠错 (Self-Correction)**：系统自带 `clarification_has_schema_contradiction` 检查。如果 LLM 产生幻觉，声称“缺少某个表或字段”但该字段其实已经由第一步的 SQLite 检索提供在 Prompt 中，系统会自动注入纠错 Prompt (`build_clarification_retry_prompt`)，在后台静默触发一次 Retry，强制 LLM 仔细重读当前 Schema，极大地提高了最终生成准确率。
- **UI 呈现**：当判定为澄清时，前端流式解析并展示类似聊天机器人的对话气泡 (`HermesProcess.vue`)，自然引导用户点击选项或补充文本。

### 3.3 流式透明度 (SSE Streaming)

后端通过 Server-Sent Events (SSE) 实时推送 AI 的每一步心智模型状态 (Phase)：

- `retrieving_schema`: "正在从 SQLite 检索候选 Schema..."
- `calling_hermes`: "正在调用 Hermes Agent..."
- `note_used`: "参考笔记: xxx"
  让"黑盒"的思考和检索过程彻底对用户透明，极大降低了等待焦虑。

## 4. 项目评分与点评

**综合得分：88 / 100 (优秀)**

### 🌟 核心亮点：

1. **防幻觉设计极其严谨务实**：结合了传统本地检索（保证 Schema 不超纲）+ RAG（Obsidian 保证业务口径正确）+ 强退澄清机制 + 正则校验防御，构成了一套可用性极高的企业级 Text-to-SQL 防御网。
2. **出色的交互体验 (UX)**：多标签页的并发工作流设计、SSE 流式过程动态展示、SQL 的打字机渐进式渲染、清爽的 Naive UI 布局，都体现了对细节的把控。
3. **架构轻量化**：没有过度设计，采用本地 SQLite 持久化和简单的目录结构作为外挂知识库，十分契合桌面级或本地轻型服务的定位。

### 🔧 改进建议 (扣分点)：

1. **强依赖外部 CLI 进程**：通过 `subprocess` 调用 `hermes` 并使用大量复杂的 Regex 来强行解析 CLI 的文本输出（包括匹配 `session_id` 和 JSON 切割），这在长期维护中非常脆弱。**建议：** 尽早迁移至直接调用大模型官方 API SDK 或使用成熟的框架如 LangChain/LlamaIndex 进行编排。
2. **高并发下的性能隐患**：`knowledge_service.py` 中的订阅通知采用了 `threading.Condition`，这在单节点少量并发尚可，但无法水平扩展；数据源测试连接 (`timeout_ms=30000`) 的同步阻塞也可能引发应用层面的卡顿。
