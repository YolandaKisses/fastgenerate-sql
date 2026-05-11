---
summary: 凭证信息表
table_type: 未知
tags:
  - db-table
  - 凭证
  - 账户
related:
  - "[[afs_budget]]"
  - "[[acco]]"
  - "[[accorequest]]"
  - "[[accountinfo_zs]]"
  - "[[agh_vjk_wbfk_zyqxx]]"
  - "[[cr_export_config]]"
  - "[[cr_export_fund]]"
  - "[[cr_fixed_tpl_excel_conf]]"
keywords:
  - vouchers
  - 凭证
  - 账户代码
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
  - afs_aiprodt_vouchers
  - acco
review_status: unreviewed
---

# 🏷️ afs_aiprodt_vouchers

[⬅️ 返回数据源总览](../index.md)

::: tip 概述
- **数据源**: `dd_etl`
- **业务说明**: 存储凭证相关数据，记录账户凭证的摘要、税种、借贷方向及规则等信息。
:::

---

## 🔗 表间关系
::: info 关联模型与推断
最可能关联对象：通过 accnt_code 字段关联客户信息表（如 acco），但字段对应关系不明确，置信度中。

- [acco](./acco.md) · 推测通过 accnt_code 关联客户信息 · `未提供` · 置信度：`中` · 依据：未提供

---

## 💡 核心字段解读
> [!quote] 业务逻辑说明
> - id: 主键标识
> - accnt_code: 账户代码，可能关联客户或账户信息
> - vc_summary: 凭证摘要，描述凭证业务内容
> - sub_taxtype: 子税种分类，推测为税务子类别
> - dc_flag: 借贷标志，推测 D 表示借（Debit），C 表示贷（Credit）
> - l_rules: 规则编号，可能关联外部规则定义
> - t0/t1/t2/t3/t5/t8: 推测为时间或状态字段，具体含义未知

---

## ⚠️ 注意事项
::: warning 风险提示
该表无原始备注及补充备注，字段含义均为推测，实际业务需进一步确认
:::

---

## 🛠️ 相关存储过程

### 🔍 命中列表
*暂无命中过程*

---

## 📋 字段明细

| 字段名 | 类型 | 原始备注 | 补充备注 |
| :--- | :--- | :--- | :--- |
| **id** | `NUMBER` |  |  |
| **accnt_code** | `VARCHAR(20)` |  |  |
| **vc_summary** | `VARCHAR(50)` |  |  |
| **sub_taxtype** | `VARCHAR(10)` |  |  |
| **dc_flag** | `VARCHAR(10)` |  |  |
| **l_rules** | `NUMBER` |  |  |
| **t0** | `VARCHAR(10)` |  |  |
| **t1** | `VARCHAR(10)` |  |  |
| **t2** | `VARCHAR(10)` |  |  |
| **t5** | `VARCHAR(10)` |  |  |
| **t8** | `VARCHAR(10)` |  |  |
| **t3** | `VARCHAR(10)` |  |  |