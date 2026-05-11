---
summary: 指令扩展信息表，记录完整业务指令相关字段。
table_type: 流水表
tags:
  - db-table
  - 指令
  - 工作流
  - 股票
  - 产品
  - 对手方
  - 金额
  - ETL
related:
  - "[[all_dictateinfoex]]"
  - "[[acco]]"
  - "[[accountinfo_zs]]"
  - "[[etl_exec_detail_log]]"
  - "[[etl_exec_main_log]]"
keywords:
  - 指令扩展
  - 业务指令
  - 工作流状态
  - 交易明细
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
  - all_dictateinfoex1
  - all_dictateinfoex
  - acco
  - accountinfo_zs
  - etl_exec_detail_log
review_status: unreviewed
---

# 🏷️ all_dictateinfoex1

[⬅️ 返回数据源总览](../index.md)

::: tip 概述
- **数据源**: `dd_etl`
- **业务说明**: 记录各类业务指令的详细扩展信息，包括工作流状态、交易金额、对手方、产品、股票等，支撑指令执行与核算。
:::

---

## 🔗 表间关系
::: info 关联模型与推断
- 关联 all_dictateinfoex (表名相似，推测为基础指令表)，通过 l_batch_no + l_serial_no 等唯一键；置信度：中。
- 关联 acco (客户基本信息表)，通过 l_rival_id 或 vc_rival_code；置信度：高。
- 关联 accountinfo_zs (帐户资料)，通过 l_account_id 或 vc_bank_account；置信度：中。
- 关联 etl_exec_detail_log / etl_exec_main_log (ETL执行日志)，通过可能存在的外键或批次号；置信度：低。

- [all_dictateinfoex](./all_dictateinfoex.md) · 扩展表 · `未提供` · 置信度：`中` · 依据：未提供
- [acco](./acco.md) · 关联客户 · `未提供` · 置信度：`高` · 依据：未提供
- [accountinfo_zs](./accountinfo_zs.md) · 关联账户 · `未提供` · 置信度：`中` · 依据：未提供
- [etl_exec_detail_log](./etl_exec_detail_log.md) · 可能ETL记录 · `未提供` · 置信度：`低` · 依据：未提供

---

## 💡 核心字段解读
> [!quote] 业务逻辑说明
> - vc_organization_code：机构代码，区分不同组织。
> - l_date / l_time：指令日期和时间，NUMBER类型可能为YYYYMMDD格式。
> - l_batch_no / l_serial_no：批次号和流水号，用于指令唯一标识。
> - wf_instance_id / wf_node_id / wf_node_name：工作流实例、节点ID和名称，标识指令审批流程。
> - c_node_status：节点状态，CHAR(1)可能枚举如0待审批、1已审批等。
> - vc_branch_id：分支机构ID。
> - l_project_id / vc_project_code：项目ID和代码。
> - vc_product_id / vc_product_id_son：产品ID和子产品ID。
> - l_workgroup_id：工作组ID。
> - c_money_type：货币类型，CHAR(1)可能为'R'人民币等。
> - l_busin_flag：业务标志，NUMBER可能表示业务类型代码。
> - vc_stock_code / vc_stock_name：股票代码和名称。
> - l_preoccur_date / l_occur_date：预计发生日期和实际发生日期，NUMBER格式。
> - en_ori_preoccur_balance / en_preoccur_balance / en_occur_balance：原始预计余额、预计余额、发生余额，EN前缀可能表示金额。
> - l_preoccur_amount / l_occur_amount：预计金额和发生金额。
> - en_busin_price：业务价格。
> - en_occur_invest：发生投资金额。
> - l_begin_date / l_end_date：开始日期和结束日期。
> - l_rival_id / l_rival_account_id / vc_rival_code / vc_rival_name相关字段：对手方ID、账户ID、代码、名称等。
> - l_account_id：本方账户ID。
> - c_ext_flag：扩展标志，VARCHAR(4)可能表示特殊处理标识。
> - vc_op_code / vc_execute_operator / vc_approve_operator / vc_review_operator：操作员、执行人、审批人、复核人编码。
> - c_exec_status：执行状态，CHAR(1)可能枚举如0未执行、1已执行。
> - en_occur_profit / en_offset_balance：发生利润、冲抵余额。
> - vc_dictate_tags：指令标签，VARCHAR(32)可能分类。
> - c_repay_type：还款类型，CHAR(1)。
> - vc_remark：备注，VARCHAR(2000)。
> - d_updatetime：更新时间，DATE类型。

---

## ⚠️ 注意事项
::: warning 风险提示
- 字段名称多简写，含义需结合业务文档确认
- c_node_status、c_exec_status等枚举值未提供
- 部分字段如vc_stock_code1用途不明确
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