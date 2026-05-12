# FastGenerate SQL LightRAG HTTP 联调契约

**日期：** 2026-05-12  
**状态：** Draft / Mock-Aligned  
**适用范围：** `api/app/services/rag/backends.py` 中 `LightRAGHTTPBackend`

---

## 1. 目的

这份文档定义当前项目默认采用的 LightRAG HTTP 联调契约。

它的作用不是声明“真实 LightRAG 服务一定长这样”，而是明确：

- 当前项目已经按什么协议预留远端接入能力
- 真实服务到位后，应优先在 `LightRAGHTTPBackend` 中做适配
- `/rag/search`、`/rag/ask`、`/rag/index/rebuild` 以及前端页面协议保持不变

---

## 2. 配置项

运行时/环境变量支持：

- `RAG_RETRIEVAL_BACKEND`
  - `local`
  - `lightrag`
- `LIGHTRAG_BASE_URL`
- `LIGHTRAG_API_KEY`
- `LIGHTRAG_TIMEOUT_SECONDS`
- `LIGHTRAG_HEALTH_PATH`
- `LIGHTRAG_SEARCH_PATH`
- `LIGHTRAG_ASK_PATH`
- `LIGHTRAG_REBUILD_PATH`
- `LIGHTRAG_UPSERT_PATH`
- `LIGHTRAG_DELETE_PATH`
- `LIGHTRAG_ENABLE_REMOTE_REBUILD`
- `LIGHTRAG_ENABLE_REMOTE_ASK`

默认行为：

- `search` 在 `lightrag` 模式下优先调用远端
- `ask` 只有在 `LIGHTRAG_ENABLE_REMOTE_ASK=true` 时才优先调用远端
- `rebuild / upsert / delete` 只有在 `LIGHTRAG_ENABLE_REMOTE_REBUILD=true` 时才尝试同步远端
- 任一远端调用失败时，系统保留本地 fallback 能力

---

## 3. 端点约定

### 3.1 Health

请求：

```http
GET {LIGHTRAG_BASE_URL}{LIGHTRAG_HEALTH_PATH}
Authorization: Bearer <LIGHTRAG_API_KEY>   # 可选
```

成功条件：

- 返回 2xx 即视为服务可用

---

### 3.2 Search

请求：

```json
POST {LIGHTRAG_BASE_URL}{LIGHTRAG_SEARCH_PATH}
{
  "query": "east 报送明细表和账户资料表的关联键是什么",
  "filters": {
    "datasource": "dd_etl",
    "source_types": ["demand", "schema"],
    "demand_name": "east报送",
    "object_type": "table"
  },
  "top_k": 8,
  "wiki_root": "/abs/path/to/wiki"
}
```

远端返回支持的候选列表字段：

- `items`
- `results`
- `chunks`

每个命中项兼容字段：

- `chunk_id` 或 `id`
- `score` 或 `similarity`
- `title` 或 `name`
- `path` 或 `source_path` 或 `file_path`
- `snippet` 或 `content` 或 `text`

metadata 兼容字段：

- `metadata.path`
- `metadata.title`
- `metadata.source_type`
- `metadata.datasource`
- `metadata.object_type`
- `metadata.object_name`

推荐远端返回：

```json
{
  "items": [
    {
      "chunk_id": "remote-1",
      "score": 0.91,
      "title": "ads_east_report_detail",
      "path": "dd_etl/demand/east报送/ads_east_report_detail.md",
      "source_type": "demand",
      "datasource": "dd_etl",
      "object_type": "table",
      "object_name": "ads_east_report_detail",
      "snippet": "cust_id 作为关联键"
    }
  ],
  "retrieval": {
    "matched_count": 1,
    "direct_hits": 1,
    "source_types": ["demand"],
    "top_k_used": 8
  },
  "diagnostics": {
    "related_entities": [],
    "related_relations": []
  }
}
```

---

### 3.3 Ask

请求：

```json
POST {LIGHTRAG_BASE_URL}{LIGHTRAG_ASK_PATH}
{
  "query": "east 报送明细表和账户资料表的关联键是什么",
  "filters": {
    "datasource": "dd_etl",
    "source_types": ["demand", "schema"]
  },
  "top_k": 8,
  "wiki_root": "/abs/path/to/wiki"
}
```

推荐远端返回：

```json
{
  "answer": "根据检索证据，关联键是 cust_id。",
  "items": [
    {
      "chunk_id": "remote-ask-1",
      "score": 0.95,
      "title": "ads_east_report_detail",
      "path": "dd_etl/demand/east报送/ads_east_report_detail.md",
      "source_type": "demand",
      "datasource": "dd_etl",
      "snippet": "cust_id 作为关联键"
    }
  ],
  "retrieval": {
    "matched_count": 1,
    "direct_hits": 1,
    "source_types": ["demand"],
    "top_k_used": 8
  },
  "diagnostics": {
    "related_entities": [],
    "related_relations": []
  }
}
```

兼容的答案字段：

- `answer`
- `response`
- `message`

---

### 3.4 Rebuild

请求：

```json
POST {LIGHTRAG_BASE_URL}{LIGHTRAG_REBUILD_PATH}
{
  "wiki_root": "/abs/path/to/wiki"
}
```

推荐返回：

```json
{
  "status": "ok",
  "indexed_files": 128,
  "indexed_chunks": 520
}
```

---

### 3.5 Upsert

请求：

```json
POST {LIGHTRAG_BASE_URL}{LIGHTRAG_UPSERT_PATH}
{
  "wiki_root": "/abs/path/to/wiki",
  "path": "dd_etl/demand/east报送/ads_east_report_detail.md"
}
```

推荐返回：

```json
{
  "status": "ok"
}
```

---

### 3.6 Delete

请求：

```json
POST {LIGHTRAG_BASE_URL}{LIGHTRAG_DELETE_PATH}
{
  "wiki_root": "/abs/path/to/wiki",
  "path": "dd_etl/demand/east报送/ads_east_report_detail.md"
}
```

推荐返回：

```json
{
  "status": "ok"
}
```

---

## 4. 回退策略

### 4.1 Search 回退

如果远端 `search` 调用失败：

- 自动回退到本地 `LocalFallbackBackend`
- `search` 接口协议不变

### 4.2 Ask 回退

如果远端 `ask` 调用失败：

- 自动回退到本地链路
- 本地链路仍为：
  - `search`
  - `ContextAssembler`
  - `HermesAnswerService`

### 4.3 索引维护回退

如果远端 `rebuild / upsert / delete` 调用失败：

- 本地索引仍然会更新
- 远端失败不会阻断需求文档保存、删除、重命名、知识同步成功后的主流程

---

## 5. 联调建议

真实 LightRAG 服务到位后，建议按以下顺序对齐：

1. `health`
2. `search`
3. `ask`
4. `rebuild`
5. `upsert`
6. `delete`

如果真实服务字段名或结构不同：

- 只修改 `LightRAGHTTPBackend`
- 不修改 `/rag/search`
- 不修改 `/rag/ask`
- 不修改前端问答页

---

## 6. 当前状态

当前项目已经具备：

- Mock 契约下的后端适配能力
- 远端优先 / 本地回退能力
- 索引维护远端同步入口
- 设置页联调配置
- `POST /settings/test/lightrag` 连通性检查

尚未完成的部分：

- 与真实可访问 LightRAG 服务的服务级联调
- 基于真实返回样例的最终协议微调
