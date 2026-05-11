---
summary: 预算科目基础信息表，包含代码、名称以及关联的账户和资金代码。
table_type: 未知
tags:
  - db-table
  - 预算
  - 科目
  - 账户
  - 资金
related:
  - "[[acco]]"
  - "[[accorequest]]"
  - "[[afs_aiprodt_vouchers]]"
keywords:
  - bugt_code
  - bugt_name
  - accnt_code
  - cash_code
project: dd_etl
type: table-note
status: active
created: 2026/05/11
updated: 2026/05/11
source: ai-generated
confidence: low
contested: False
source_routines:
source_tables:
  - afs_budget
  - acco
  - accorequest
  - afs_aiprodt_vouchers
review_status: unreviewed
---

# 🏷️ afs_budget

[⬅️ 返回数据源总览](../index.md)

::: tip 概述
- **数据源**: `dd_etl`
- **业务说明**: 存储预算科目的基本信息和关联的账户及资金代码。
:::

---

## 🔗 表间关系
::: info 关联模型与推断
- 关联 acco（通过 accnt_code 关联，推测为账户信息，置信度：中）
- 关联 accorequest（通过 accnt_code 关联，推测为账户确认信息，置信度：中）
- 关联 afs_aiprodt_vouchers（名称或上下文相关，置信度：低）

- [acco](./acco.md) · 推测关联 · `未提供` · 置信度：`中` · 依据：未提供
- [accorequest](./accorequest.md) · 推测关联 · `未提供` · 置信度：`中` · 依据：未提供
- [afs_aiprodt_vouchers](./afs_aiprodt_vouchers.md) · 名称相关 · `未提供` · 置信度：`低` · 依据：未提供

---

## 💡 核心字段解读
> [!quote] 业务逻辑说明
> - bugt_code: 预算科目代码
> - bugt_name: 预算科目名称
> - accnt_code: 账户代码
> - cash_code: 资金代码

---

## ⚠️ 注意事项
::: warning 风险提示
字段含义及表用途基于表名和字段名推测，无明确备注或外键信息支撑
:::

---

## 🛠️ 相关存储过程

### 🔍 命中列表
*暂无命中过程*

---

## 📋 字段明细

| 字段名 | 类型 | 原始备注 | 补充备注 |
| :--- | :--- | :--- | :--- |
| **bugt_code** | `VARCHAR(20)` |  |  |
| **bugt_name** | `VARCHAR(100)` |  |  |
| **accnt_code** | `VARCHAR(100)` |  |  |
| **cash_code** | `VARCHAR(20)` |  |  |