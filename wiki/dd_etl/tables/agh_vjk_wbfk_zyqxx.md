---
summary: 回购质押券信息表，记录产品代码、证券内码、数量及折算比例等核心要素。
table_type: 流水表
tags:
  - db-table
  - 回购
  - 质押券
  - 证券
  - 产品代码
related:
  - "[[vjk_wbfk_gzb]]"
  - "[[acco]]"
  - "[[accorequest]]"
  - "[[accountinfo_zs]]"
  - "[[cr_export_config]]"
keywords:
  - 回购质押券
  - 产品代码
  - 证券内码
  - 数量
  - 折算比例
project: dd_etl
type: table-note
status: active
created: 2026/05/11
updated: 2026/05/11
source: ai-generated
confidence: high
contested: False
source_routines:
source_tables:
  - agh_vjk_wbfk_zyqxx
  - vjk_wbfk_gzb
  - acco
review_status: unreviewed
---

# 🏷️ agh_vjk_wbfk_zyqxx

[⬅️ 返回数据源总览](../index.md)

::: tip 概述
- **数据源**: `dd_etl`
- **业务说明**: 存储回购业务中质押券的明细信息，包括产品代码、证券内码、数量、折算比例及创建日期等，支持文件导入方式补充数据。
:::

---

## 🔗 表间关系
::: info 关联模型与推断
- 与 vjk_wbfk_gzb（回购质押券工作簿表）可能通过产品代码关联，用于扩展质押券工作信息
- 与 acco（客户基本信息表）、accorequest（账户确认信息表）等可能存在间接关联，字段对应关系不明朗。

- [vjk_wbfk_gzb](./vjk_wbfk_gzb.md) · 推测关联字段: vc_cpdm · `未提供` · 置信度：`中` · 依据：未提供
- [acco](./acco.md) · 推测通过产品代码间接关联 · `未提供` · 置信度：`低` · 依据：未提供

---

## 💡 核心字段解读
> [!quote] 业务逻辑说明
> - vc_cpdm：产品代码，标识质押券所属的产品。
> - l_zqnm：证券内码，证券的唯一内部编码。
> - l_bh：流水编号，业务流水标识。
> - en_sl：数量，质押券的数量。
> - en_zsbl：折算比例，质押券按市值折算的比例。
> - d_cjrq：创建日期，记录的创建日期。
> - vc_isin：国际证券识别码（推测），无备注。
> - vc_fundcode：产品代码（文件导入使用），导入时的外部产品代码。
> - vc_source：数据来源（文件导入使用），标识导入数据的来源。
> - d_filedate：文件日期（文件导入使用），导入文件的日期。

---

## ⚠️ 注意事项
::: warning 风险提示
- 字段 vc_isin 无备注，推测为国际证券识别码
- vc_fundcode、vc_source、d_filedate 为文件导入辅助字段，可能非核心业务字段
:::

---

## 🛠️ 相关存储过程

### 🔍 命中列表
*暂无命中过程*

---

## 📋 字段明细

| 字段名 | 类型 | 原始备注 | 补充备注 |
| :--- | :--- | :--- | :--- |
| **vc_cpdm** | `VARCHAR(56)` | 产品代码 |  |
| **l_zqnm** | `NUMBER` | 证券内码 |  |
| **l_bh** | `NUMBER` | 流水编号 |  |
| **en_sl** | `NUMBER` | 数量 |  |
| **en_zsbl** | `NUMBER` | 折算比例 |  |
| **d_cjrq** | `DATE` | 创建日期 |  |
| **vc_isin** | `VARCHAR(20)` |  |  |
| **vc_fundcode** | `VARCHAR(20)` | 产品代码(文件导入使用) |  |
| **vc_source** | `VARCHAR(20)` | 数据来源(文件导入使用) |  |
| **d_filedate** | `VARCHAR(20)` | 文件日期(文件导入使用) |  |