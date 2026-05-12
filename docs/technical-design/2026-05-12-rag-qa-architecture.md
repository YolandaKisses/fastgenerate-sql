# FastGenerate SQL RAG 问答链路技术方案

**日期：** 2026-05-12  
**状态：** Draft  
**适用范围：** FastGenerate SQL 本地知识库问答、Wiki 检索、元数据辅助问答

---

## 1. 目标

在现有 `Wiki` 浏览和“知识库同步”能力之上，新增一套真正可用的问答检索链路，使用户能够：

- 输入自然语言问题
- 基于本地 `wiki/` 文档、需求文档、表结构、血缘信息检索相关证据
- 由 LLM 基于检索证据生成答案
- 查看答案引用来源、召回证据、命中文档
- 一键跳回 Wiki 页面查看原文

这套方案的核心不是“把 Markdown 展示给用户”，而是提供一条完整的：

`问题 -> 检索 -> 上下文组装 -> LLM 回答 -> 引用返回 -> 前端展示`

问答链路。

---

## 2. 当前现状

当前仓库已经具备：

- 后端知识同步能力：`api/app/services/knowledge_service.py`
- 本地 Wiki 文件树读取：`api/app/api/routes/wiki.py`
- 前端 Markdown 浏览页：`src/pages/Wiki/index.vue`
- 元数据、视图、存储过程、血缘等本地沉淀内容
- 新增的需求文档：`wiki/{datasource}/demand/...`

但当前缺少以下关键能力：

- 没有统一索引层
- 没有问答入口接口
- 没有检索召回和排序
- 没有将检索结果组装进 LLM prompt
- 没有“答案 + 引用 + 召回证据”的前端展示页

因此当前系统更接近“知识沉淀 + 文档浏览”，而不是“知识问答系统”。

---

## 3. 总体架构

```text
[用户]
   ↓ 提问
[前端 Vue]
   ↓ POST /api/v1/rag/ask 或 /api/v1/rag/search
[后端 FastAPI]
   ↓
[IndexManager]
   ├─ 扫描/索引本地 wiki/**/*.md
   ├─ 维护全量/增量索引
   └─ 保存文件 hash / mtime / metadata
   ↓
[Retriever / LightRAG 封装层]
   ├─ 检索 chunk
   ├─ 检索实体 / 关系
   ├─ 按 source_type / datasource 过滤
   └─ 返回相关证据
   ↓
[ContextAssembler]
   ├─ top-k 召回去重
   ├─ 分桶组织证据
   ├─ 拼接系统提示词
   └─ 输出 LLM prompt
   ↓
[Hermes]
   ├─ 依据检索上下文回答
   └─ 返回答案和引用说明
   ↓
[后端]
   ├─ answer
   ├─ sources
   └─ retrieval diagnostics
   ↓
[前端]
   ├─ 展示答案
   ├─ 展示引用
   └─ 展示召回证据并跳转 Wiki
```

---

## 4. 模块设计

### 4.1 IndexManager

职责：

- 统一管理本地知识源索引
- 支持全量重建
- 支持单文件增量更新
- 记录文件状态（`hash` / `mtime` / `indexed_at`）

建议新增文件：

- `api/app/services/rag/index_manager.py`
- `api/app/services/rag/source_loader.py`
- `api/app/services/rag/file_state_store.py`

建议行为：

- `rebuild_all_indexes()`：全量重建
- `index_single_file(path)`：单文件增量更新
- `detect_changed_files()`：比较 `hash/mtime`
- `remove_deleted_file(path)`：删除已失效索引

优先级：

- 第一阶段只做“手工触发全量重建 + 单文件增量”
- 暂不一开始实现复杂 watcher

---

### 4.2 Knowledge Source Loader

职责：

- 扫描并标准化本地知识源
- 为每个文档附加统一 metadata

纳入索引的知识源范围建议：

- `wiki/{datasource}/tables/**/*.md`
- `wiki/{datasource}/views/**/*.md`
- `wiki/{datasource}/routines/**/*.md`
- `wiki/{datasource}/terms/**/*.md`
- `wiki/{datasource}/demand/**/*.md`
- 同步日志导出文本（如有）
- 血缘说明文档（如有）

统一 metadata 结构建议：

```json
{
  "source_type": "demand",
  "datasource": "dd_etl",
  "object_type": "table",
  "object_name": "ads_east_report_detail",
  "path": "dd_etl/demand/east报送/ads_east_report_detail.md",
  "title": "ads_east_report_detail",
  "category": "east报送"
}
```

`source_type` 建议限定枚举：

- `wiki`
- `schema`
- `lineage`
- `log`
- `demand`

这是后续过滤、调权、排障的关键。

---

### 4.3 Retriever / LightRAG 封装层

职责：

- 调用 LightRAG 完成召回
- 负责过滤、排序和基础归一化输出

建议新增文件：

- `api/app/services/rag/retriever.py`
- `api/app/services/rag/lightrag_client.py`

建议方法：

- `search(query, filters, top_k)`
- `ask(query, filters, top_k)`
- `get_related_entities(query)`
- `get_related_relations(query)`

过滤条件建议支持：

- `datasource`
- `source_types`
- `demand_name`
- `object_type`

返回的召回结果建议统一为：

```json
{
  "chunk_id": "chunk-001",
  "score": 0.82,
  "title": "ads_east_report_detail",
  "path": "dd_etl/demand/east报送/ads_east_report_detail.md",
  "source_type": "demand",
  "datasource": "dd_etl",
  "object_type": "table",
  "object_name": "ads_east_report_detail",
  "snippet": "..."
}
```

---

### 4.4 ContextAssembler

职责：

- 从检索结果里选出真正要喂给 LLM 的上下文
- 去重、裁剪、按类型分桶

建议新增文件：

- `api/app/services/rag/context_assembler.py`
- `api/app/services/rag/prompt_builder.py`

建议规则：

- 不直接把 top-k 全塞给 LLM
- 同一文档相邻 chunk 去重
- 优先保留“直接命中对象”
- 补充“关联对象”和“需求文档”

建议分桶：

- 直接命中对象
- 关联对象
- 需求/术语说明
- 血缘/过程证据

Prompt 组成建议：

1. 系统提示词
2. 用户问题
3. 检索证据（带来源路径）
4. 回答要求（必须引用、不可编造）

---

### 4.5 Hermes Answer Service

职责：

- 负责把检索后组装好的 prompt 交给 Hermes
- 对 Hermes 的输出做统一清洗
- 在问答接口层返回标准化的 `answer + sources + retrieval`

建议复用/扩展现有能力：

- `api/app/services/hermes_service.py`

建议新增文件：

- `api/app/services/rag/hermes_answer_service.py`

建议方法：

- `answer_with_hermes(query, context, prompt_config)`
- `format_hermes_answer(raw_output)`
- `fallback_when_no_evidence(query, retrieval_summary)`

关键约束：

- Hermes 不直接裸答
- Hermes 必须只基于检索证据回答
- 如果证据不足，Hermes 应明确说“当前证据不足以确认”

推荐系统提示词约束：

- 只能依据给定上下文回答
- 不得补造不存在的表、字段、血缘关系
- 如果检索结果冲突，应指出冲突来源
- 回答后保留引用来源摘要

---

## 5. 接口设计

### 5.1 检索接口

`POST /api/v1/rag/search`

请求：

```json
{
  "query": "east 报送表和账户资料表有什么关系",
  "datasource": "dd_etl",
  "source_types": ["demand", "schema"],
  "top_k": 8
}
```

响应：

```json
{
  "items": [
    {
      "chunk_id": "chunk-001",
      "score": 0.83,
      "title": "ads_east_report_detail",
      "path": "dd_etl/demand/east报送/ads_east_report_detail.md",
      "source_type": "demand",
      "datasource": "dd_etl",
      "object_type": "table",
      "object_name": "ads_east_report_detail",
      "snippet": "..."
    }
  ],
  "retrieval": {
    "matched_count": 8,
    "direct_hits": 3,
    "source_types": ["demand", "schema"],
    "top_k_used": 8
  }
}
```

### 5.2 问答接口

`POST /api/v1/rag/ask`

请求：

```json
{
  "query": "east 报送明细表和账户资料表的关联键是什么",
  "datasource": "dd_etl",
  "source_types": ["demand", "schema", "lineage"],
  "top_k": 8
}
```

响应：

```json
{
  "answer": "根据需求文档与表结构说明，ads_east_report_detail 与 accountinfo_zs 的关联键通常为 ...",
  "sources": [
    {
      "title": "ads_east_report_detail",
      "path": "dd_etl/demand/east报送/ads_east_report_detail.md",
      "source_type": "demand",
      "snippet": "..."
    }
  ],
  "retrieval": {
    "matched_count": 8,
    "direct_hits": 3,
    "source_types": ["demand", "schema"],
    "top_k_used": 8
  }
}
```

说明：

- `ask` 必须返回 `answer + sources + retrieval`
- 不能只返回最终答案
- `ask` 内部由 Hermes 负责答案生成，而不是通用模型执行器

---

## 6. 前端页面设计

建议新增页面：

- `src/pages/RagQa/index.vue`

建议页面布局：**双栏**

### 左栏：问答结果

- 问题输入框
- 数据源过滤
- 来源类型过滤
- 提交按钮
- 答案展示区
- 引用来源列表

### 右栏：召回证据

- 检索命中条数
- 命中文档列表
- 每个命中的片段预览
- 点击跳转到 Wiki

这和当前已有的 Wiki 浏览页配合很好：

- 右栏点某条来源
- 跳到 `#/wiki?path=...`
- 直接看原始文档

---

## 7. 索引更新策略

### 7.0 交互原则

用户**不应该**在每次“知识库同步”完成后，再手动点击一次“建立索引”。

推荐产品行为：

- 第一次启用问答能力时：
  - 提供一次 `全量重建索引` 入口
- 日常使用时：
  - 知识库同步完成后自动触发增量索引
  - 需求文档保存后自动触发增量索引
  - 需求文档删除/重命名后自动触发增量索引或删除索引

也就是说：

- **全量重建** 是初始化/修复工具
- **增量更新** 是日常默认路径

建议在产品上只保留一个偏运维性质的按钮：

- `重建问答索引`

这个按钮建议放在：

- 本地设置页
- 或知识库管理页

它的用途应明确限定为：

- 首次初始化索引
- 索引损坏后的修复
- 目录结构规则变化后的重建
- 系统未能感知的大批量历史文档变更后的补救

### 7.1 第一阶段

- 手动全量重建
- 单文件增量更新

### 7.2 第二阶段

- 记录文件 `mtime/hash`
- 每次问答前做轻量变更检测
- 将变更文件送入增量索引队列

### 7.3 第三阶段

- 可选文件监听器
- 自动增量重建

建议不要一开始就实现复杂 watcher。优先把：

- 全量重建
- 单文件增量
- 文件状态持久化

这三件事做稳定。

### 7.4 推荐触发时机

#### 自动触发增量更新

以下动作完成后，系统应自动触发索引更新：

- 元数据/脚本/知识库同步成功后
- 需求文档保存成功后
- 需求文档删除后
- 需求分类重命名或移动后（若影响路径）

#### 手动触发全量重建

仅在以下场景建议用户手动点击：

- 第一次启用问答功能
- 索引文件损坏或版本不兼容
- 历史 Wiki 文档被批量外部改动
- 检索行为异常，需要从头重建确认问题

---

## 8. 和现有能力的集成点

### 8.1 与知识同步集成

当前 `knowledge_service.py` 已经负责生成 wiki 文档。  
新增要求：

- 每次知识同步成功后，可触发索引增量更新
- 或至少标记“索引待重建”

### 8.2 与需求管理集成

当前需求管理保存需求文档后：

- 需求 Markdown 已落盘
- 下一步应触发该文件的单文件增量索引

### 8.3 与 Wiki 页面集成

当前 `Wiki` 页面已经支持 `path` 打开文档。  
RAG 结果只需要返回：

- `path`
- `title`
- `snippet`

前端即可复用已有跳转能力。

### 8.4 与 Hermes 集成

当前仓库已经有 Hermes 调用基础：

- `api/app/services/hermes_service.py`

因此问答链路不需要重新引入另一套聊天模型调用框架，而应优先复用现有 Hermes 能力。

推荐集成方式：

1. `Retriever` 检索证据
2. `ContextAssembler` 组装上下文
3. `HermesAnswerService` 调用 Hermes
4. `rag.py` 路由返回标准化问答结果

不建议的方式：

- 前端直接调 Hermes 做问答
- 后端跳过检索，直接把问题交给 Hermes
- 只返回 Hermes 文本，不返回召回证据

---

## 9. 推荐目录结构

```text
api/app/services/rag/
  __init__.py
  index_manager.py
  retriever.py
  context_assembler.py
  hermes_answer_service.py
  prompt_builder.py
  source_loader.py
  file_state_store.py
  schemas.py

api/app/api/routes/
  rag.py

src/pages/RagQa/
  index.vue
  components/
    AskPanel.vue
    AnswerPanel.vue
    RetrievalPanel.vue
```

---

## 10. 分阶段交付建议

### Phase 1：最小可用版

目标：

- 可检索
- 可问答
- 可返回引用

范围：

- `POST /rag/search`
- `POST /rag/ask`
- 手动全量建索引
- 双栏问答页初版

### Phase 2：工程可用版

目标：

- 文档变更后可增量更新
- 回答可调试

范围：

- 单文件增量索引
- `hash/mtime` 管理
- `answer + sources + retrieval` 标准化
- `source_type` 过滤

### Phase 3：体验增强版

目标：

- 更自动化
- 更低维护成本

范围：

- 文件监听
- 更细粒度过滤
- 多跳关系检索
- 会话上下文问答

---

## 11. Hermes 接入约束

### 11.1 Hermes 在链路中的角色

Hermes 是这套方案里的“答案生成器”，不是检索系统本身。

也就是说：

- 检索是否命中，由 Retriever 决定
- 证据是否充分，由 ContextAssembler 和 retrieval summary 决定
- 最终语言表达，由 Hermes 生成

因此不能把“调用 Hermes”误认为“已经实现 RAG”。

### 11.2 Hermes 输入建议

建议 Hermes 输入包含以下部分：

1. 系统约束
2. 用户问题
3. 检索到的证据片段
4. 来源路径和来源类型
5. 回答格式要求

示例结构：

```text
你是 FastGenerate SQL 的知识问答助手。
你只能依据提供的证据回答问题。
如果证据不足，请明确说明“当前证据不足”。

[用户问题]
...

[检索证据]
来源1: ...
来源2: ...

[回答要求]
1. 先给出结论
2. 再给出依据
3. 引用关键来源
```

### 11.3 Hermes 输出处理

后端不能直接把 Hermes 原始输出原封不动返回给前端。

建议处理：

- 去掉多余前后缀
- 保底 answer 文本不为空
- 即使 Hermes 输出异常，也保留 retrieval 结果

标准返回仍然应保持：

```json
{
  "answer": "...",
  "sources": [...],
  "retrieval": {
    "matched_count": 8,
    "direct_hits": 3,
    "source_types": ["demand", "schema"]
  }
}
```

### 11.4 Hermes 异常场景

建议显式处理：

- Hermes 超时
- Hermes 返回空文本
- Hermes 输出格式异常
- Hermes 回答与检索证据明显不一致

出现异常时，接口也不应丢失检索结果，至少应返回：

- `answer`: 错误提示或降级文案
- `sources`: 检索来源
- `retrieval`: 命中摘要

---

## 12. 风险与注意事项

1. 不要让 LLM 直接脱离检索回答。  
   在本方案里，这条规则同样适用于 Hermes。

2. 不要把“命中分数”伪装成“置信度”。  
   初期返回 `matched_count`、`direct_hits`、`top_k_used` 更真实。

3. Wiki 文件质量会直接影响 RAG 效果。  
   需求文档、表结构、血缘说明应尽量结构化。

4. 同一问题可能同时命中：
   - schema
   - demand
   - lineage  
   上下文组装器必须做去重和分桶。

---

## 13. 结论

这套方案适合当前仓库现状，原因是：

- 已有 Wiki 目录体系
- 已有知识同步生成能力
- 已有本地文档浏览器
- 已有需求文档沉淀能力

缺少的只是：

- 索引层
- 检索层
- 上下文组装层
- Hermes 问答封装层
- 问答接口
- 问答前端页

因此推荐路线不是推倒重来，而是在现有“知识沉淀 + Wiki 浏览”能力上，补出一条完整 RAG 问答链路。
