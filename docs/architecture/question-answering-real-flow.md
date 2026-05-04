# 问答真实链路

**状态**：当前工程基线  
**更新时间**：2026-05-04

本文档固定当前项目的自然语言问答真实链路，避免再回到“自然语言 -> Obsidian 全文搜索 -> 生成 SQL”的旧口径。

## 1. 总原则

当前问答链路是：

```text
自然语言问题
-> 后端准入检查
-> SQLite Schema Context 检索
-> 相关 Obsidian 表卡片补充
-> Hermes 歧义判断 / 关系补全 / SQL 生成
-> 结构校验
-> SQL 只读校验
-> SQL Schema 字段校验
-> 前端展示
-> 用户确认
-> 执行 SQL
-> 审计日志更新
```

SQLite 是事实来源和主检索层。Obsidian 是人类可读说明层。Hermes 是受控上下文内的判断和生成器。校验器是 SQL 进入执行前的最后关口。

## 2. 谁负责检索

检索由后端负责，不由 Hermes 直接扫全量 Obsidian。

后端在工作台问答开始后发送 `status.phase = retrieving_schema`，然后基于当前问题和最近用户消息构造检索问题，从 SQLite 中查找相关：

- database / schema / table
- column
- type
- nullable
- default
- comment
- primary key
- foreign key
- index
- relation hints

检索得到的结构化片段组成 `Schema Context`。后端再根据命中的相关表读取对应 Obsidian Markdown 片段，形成 `Obsidian Notes`。

多轮澄清时，后端不能只用用户最新短回复检索。例如用户回复 `A`、`是`、`第一个` 时，必须结合最近对话重新构造检索问题，避免 Schema Context 丢失。

## 3. 谁负责歧义

歧义判断由 Hermes 负责，但只能在后端提供的受控上下文内判断。

Hermes 应在以下情况返回 `clarification`：

- 多个表都可能满足问题目标。
- 同一业务词可能映射多个字段。
- 统计口径不明确。
- 时间边界不明确。
- Schema Context 和 Obsidian Notes 无法稳定收敛。
- 问题语义过于模糊。

后端负责把 Hermes 的 `clarification` 结果结构化返回前端，并在后续轮次携带最近上下文继续检索和生成。

## 4. 谁负责关系补全

关系补全由 Hermes 在受控上下文内负责。

后端提供候选表、字段、备注和已知关系线索。Hermes 可以基于这些信息推断 join 路径，但必须遵守：

- 优先使用明确外键、命名一致的字段和知识卡片里的关联说明。
- 不确定的关系必须保守处理，必要时先澄清。
- 不能使用上下文之外的表或字段。
- 不能为了让 SQL 看起来完整而编造字段。

后端不在本地硬编码复杂 join 推理，但会通过 SQL Schema 字段校验拦截明确不存在的表字段引用。

## 5. 谁负责校验

校验由后端负责，分两层。

第一层是结果结构校验：

- Hermes 必须返回 JSON。
- 顶层类型只能是 `clarification` 或 `sql_candidate`。
- `sql_candidate` 必须包含可读 SQL。

第二层是 SQL 执行前校验：

- 只允许只读查询。
- 禁止多语句。
- 禁止 DDL / DML / 写操作和明显有副作用调用。
- 限定表字段引用如果不存在，必须阻断。
- 未限定字段无法稳定确认时，降级为 warning。

校验失败时，前端不得进入执行确认。用户手动确认之后，系统才允许执行 SQL。

## 6. 前端展示责任

前端负责展示链路过程，不负责做事实判断。

工作台过程面板应区分：

- `retrieving_schema`：系统正在检索 SQLite Schema Context。
- `note_used`：系统读取了相关 Obsidian 表卡片。
- `hermes_trace`：Hermes 正在判断或生成。
- `result`：返回澄清或 SQL 候选。
- `error`：链路失败。

其中 `retrieving_schema` 属于 system 动作，不属于 Hermes 动作。

## 7. 审计责任

后端负责记录问答和执行日志：

- 当前问题
- 数据源快照
- 是否触发澄清
- 澄清内容
- 生成 SQL
- used notes
- 是否执行
- 执行状态
- 耗时
- 错误摘要

生成和执行通过 `audit_log_id` 绑定。执行 SQL 时必须回传同一个 `audit_log_id`，让历史记录可以从问题追溯到执行结果。
