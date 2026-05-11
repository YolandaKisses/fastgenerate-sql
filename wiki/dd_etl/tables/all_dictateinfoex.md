---
summary: ETF或股票交易委托指令明细表，包含工作流审批、资金变动、对手方等完整信息。
table_type: 流水表
tags:
  - db-table
  - 金融
  - 交易
  - 委托
  - 工作流
related:
  - "[[all_dictateinfoex1]]"
  - "[[acco]]"
  - "[[accountinfo_zs]]"
  - "[[etl_exec_detail_log]]"
  - "[[etl_exec_main_log]]"
keywords:
  - 委托指令
  - 交易流水
  - 工作流
  - 资金余额
  - 对手方
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
  - all_dictateinfoex
  - acco
  - accountinfo_zs
  - all_dictateinfoex1
review_status: unreviewed
---

# 🏷️ all_dictateinfoex

[⬅️ 返回数据源总览](../index.md)

::: tip 概述
- **数据源**: `dd_etl`
- **业务说明**: 记录金融交易委托指令的详细信息，包括业务流程、工作流审批、资金变动及对手方信息，用于追踪交易执行与状态变化。
:::

---

## 🔗 表间关系
::: info 关联模型与推断
- 与 all_dictateinfoex1 为结构相同的分表，通过流水号关联。
- 与 acco（客户基本信息）通过 vc_rival_code 或 l_rival_id 关联，获取客户详情。
- 与 accountinfo_zs（账户资料）通过 vc_bank_account 或 l_account_id 关联。

- [acco](./acco.md) · 外键关联 · `未提供` · 置信度：`中` · 依据：未提供
- [accountinfo_zs](./accountinfo_zs.md) · 外键关联 · `未提供` · 置信度：`中` · 依据：未提供
- [all_dictateinfoex1](./all_dictateinfoex1.md) · 同名分表 · `未提供` · 置信度：`高` · 依据：未提供

---

## 💡 核心字段解读
> [!quote] 业务逻辑说明
> - vc_organization_code: 组织机构编码（VARCHAR(8)），标识所属机构。
> - l_date/l_time: 交易日期和时间（NUMBER），精确到数字格式。
> - l_batch_no/l_serial_no: 批次号和流水号（NUMBER），唯一标识一笔委托。
> - wf_instance_id/wf_node_id/wf_node_name: 工作流实例、节点ID及名称，表示审批流程。
> - c_node_status: 工作流节点状态（CHAR(1)），枚举值可能表示待审批、已通过等。
> - vc_branch_id: 分支机构编码（VARCHAR(64)）。
> - l_project_id/vc_product_id/l_workgroup_id: 项目、产品、工作组标识。
> - c_money_type: 资金类型（CHAR(1)），可能区分币种或资金性质。
> - l_busin_flag: 业务标志（NUMBER），业务种类。
> - vc_stock_code/vc_stock_name: 股票代码和名称。
> - en_preoccur_balance/en_occur_balance: 发生前/后余额（NUMBER），金额数值。
> - l_preoccur_amount/l_occur_amount: 发生前/后数量或金额。
> - en_busin_price: 交易价格（NUMBER）。
> - en_occur_invest: 发生投资额（NUMBER）。
> - l_rival_id/l_account_id: 对手方和账户ID。
> - c_exec_status: 执行状态（CHAR(1)），如已执行、未执行。
> - vc_remark: 备注（VARCHAR(2000)），补充说明。
> - d_updatetime: 更新时间（DATE）。

---

## ⚠️ 注意事项
::: warning 风险提示
字段名采用非标准命名（如 en_ 前缀表示金额），无明确备注，业务含义基于字段名推测，部分枚举值需结合业务系统确认
:::

---

## 🛠️ 相关存储过程

### 🔍 命中列表
*暂无命中过程*

---

## 📋 字段明细

| 字段名 | 类型 | 原始备注 | 补充备注 |
| :--- | :--- | :--- | :--- |
| **vc_organization_code** | `VARCHAR(8)` |  |  |
| **l_date** | `NUMBER` |  |  |
| **l_time** | `NUMBER` |  |  |
| **l_batch_no** | `NUMBER` |  |  |
| **l_serial_no** | `NUMBER` |  |  |
| **wf_instance_id** | `VARCHAR(255)` |  |  |
| **wf_node_id** | `VARCHAR(255)` |  |  |
| **wf_node_name** | `VARCHAR(255)` |  |  |
| **c_node_status** | `CHAR(1)` |  |  |
| **vc_branch_id** | `VARCHAR(64)` |  |  |
| **l_project_id** | `NUMBER` |  |  |
| **vc_product_id** | `VARCHAR(50)` |  |  |
| **l_workgroup_id** | `NUMBER` |  |  |
| **c_money_type** | `CHAR(1)` |  |  |
| **l_busin_flag** | `NUMBER` |  |  |
| **vc_stock_code** | `VARCHAR(255)` |  |  |
| **vc_stock_name** | `VARCHAR(255)` |  |  |
| **l_preoccur_date** | `NUMBER` |  |  |
| **l_occur_date** | `NUMBER` |  |  |
| **en_ori_preoccur_balance** | `NUMBER` |  |  |
| **en_preoccur_balance** | `NUMBER` |  |  |
| **en_occur_balance** | `NUMBER` |  |  |
| **l_preoccur_amount** | `NUMBER` |  |  |
| **l_occur_amount** | `NUMBER` |  |  |
| **en_busin_price** | `NUMBER` |  |  |
| **en_occur_invest** | `NUMBER` |  |  |
| **l_begin_date** | `NUMBER` |  |  |
| **l_end_date** | `NUMBER` |  |  |
| **l_rival_id** | `NUMBER` |  |  |
| **l_account_id** | `NUMBER` |  |  |
| **l_rival_account_id** | `NUMBER` |  |  |
| **c_ext_flag** | `VARCHAR(4)` |  |  |
| **vc_op_code** | `VARCHAR(64)` |  |  |
| **vc_execute_operator** | `VARCHAR(64)` |  |  |
| **vc_approve_operator** | `VARCHAR(64)` |  |  |
| **c_exec_status** | `CHAR(1)` |  |  |
| **vc_relative_id** | `VARCHAR(255)` |  |  |
| **l_transfer_account_id** | `NUMBER` |  |  |
| **en_reserve** | `NUMBER` |  |  |
| **en_occur_profit** | `NUMBER` |  |  |
| **en_offset_balance** | `NUMBER` |  |  |
| **vc_iou_no** | `VARCHAR(32)` |  |  |
| **vc_dictate_tags** | `VARCHAR(32)` |  |  |
| **c_repay_type** | `CHAR(1)` |  |  |
| **l_att_serial** | `NUMBER` |  |  |
| **vc_remark** | `VARCHAR(2000)` |  |  |
| **l_loanrivalholder_no** | `NUMBER` |  |  |
| **l_loanrivalofficers_no** | `NUMBER` |  |  |
| **l_loarivalfamily_no** | `NUMBER` |  |  |
| **vc_stock_code1** | `VARCHAR(32)` |  |  |
| **vc_asset_code** | `VARCHAR(32)` |  |  |
| **vc_review_operator** | `VARCHAR(64)` |  |  |
| **c_deliver_status** | `CHAR(1)` |  |  |
| **combi_id** | `NUMBER` |  |  |
| **vc_project_code** | `VARCHAR(36)` |  |  |
| **vc_rival_code** | `VARCHAR(32)` |  |  |
| **vc_bank_account** | `VARCHAR(120)` |  |  |
| **c_business_class** | `CHAR(1)` |  |  |
| **vc_product_id_son** | `VARCHAR(50)` |  |  |
| **vc_turn_opcodes** | `VARCHAR(2000)` |  |  |
| **c_turn_flag** | `CHAR(1)` |  |  |
| **vc_risk_flag** | `VARCHAR(2)` |  |  |
| **en_apply_balance** | `NUMBER` |  |  |
| **en_back_balance** | `NUMBER` |  |  |
| **vc_rival_product_id** | `VARCHAR(50)` |  |  |
| **l_rival_combi_id** | `NUMBER` |  |  |
| **vc_rival_stock_code** | `VARCHAR(255)` |  |  |
| **en_rival_occur_invest** | `NUMBER` |  |  |
| **vc_op_ip** | `VARCHAR(32)` |  |  |
| **vc_source** | `VARCHAR(10)` |  |  |
| **d_updatetime** | `DATE` |  |  |