---
summary: 账户资料表，存储投资人的基本信息、基金账号、交易账号、证件信息及账户状态等核心数据，是基金销售系统的基础表。
table_type: 维表
tags:
  - db-table
  - 账户信息
  - 投资人
  - 基金
  - 交易账号
related:
  - "[[acco]]"
  - "[[accorequest]]"
keywords:
  - 基金账号
  - 交易账号
  - 账户状态
  - 投资人信息
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
  - accountinfo_zs
  - acco
  - accorequest
review_status: unreviewed
---

# 🏷️ accountinfo_zs

[⬅️ 返回数据源总览](../index.md)

::: tip 概述
- **数据源**: `dd_etl`
- **业务说明**: 存储投资人账户基本信息及交易账户状态，用于基金管理人对投资者账户的日常管理、交易确认与对账。
:::

---

## 🔗 表间关系
::: info 关联模型与推断
最核心关联：账户信息表 (accountinfo_zs) 与客户基本信息表 (acco) 通过 taaccountid 关联，置信度高。同时与账户确认信息表 (accorequest) 通过 taaccountid 和 transactionaccountid 关联，置信度中等。

- [acco](./acco.md) · 外键关联 · `未提供` · 置信度：`高` · 依据：未提供
- [accorequest](./accorequest.md) · 逻辑关联 · `未提供` · 置信度：`中` · 依据：未提供

---

## 💡 核心字段解读
> [!quote] 业务逻辑说明
> - 核心字段包括：
> - taaccountid：投资人基金账号（TA账号），唯一标识投资者在TA系统中的账户。
> - transactionaccountid：投资人交易账号，用于交易识别。
> - investorname：投资人户名。
> - accountstatus：基金帐户状态，枚举值：0-正常，1-冻结，2-挂失，3-注销，4-挂帐，5-休眠。
> - individualorinstitution：个人/机构标志，0-机构，1-个人。
> - certificatetype：证件类型，如身份证、护照等。
> - certificateno：证件号码。
> - branchcode：托管网点编号。
> - distributorcode：销售人代码。

---

## ⚠️ 注意事项
::: warning 风险提示
字段 accountstatus 和 individualorinstitution 有明确的枚举值，需注意业务逻辑一致性。部分字段如 vc_source、d_filedate、d_update 可能为系统处理字段，无业务含义
:::

---

## 🛠️ 相关存储过程

### 🔍 命中列表
*暂无命中过程*

---

## 📋 字段明细

| 字段名 | 类型 | 原始备注 | 补充备注 |
| :--- | :--- | :--- | :--- |
| **address** | `VARCHAR(60)` | 通讯地址 |  |
| **instrepridcode** | `VARCHAR(20)` | 法人代表身份证件代码 |  |
| **instrepridtype** | `VARCHAR(5)` | 法人代表证件类型 |  |
| **instreprname** | `VARCHAR(20)` | 法人代表姓名 |  |
| **appsheetserialno** | `VARCHAR(30)` | 申请单编号 |  |
| **acctnooffminclearingagency** | `VARCHAR(30)` | 基金管理人在资金清算机构的交收账号 |  |
| **acctnameoffminclearingagency** | `VARCHAR(60)` | 基金管理人在资金清算机构的交收帐户名 |  |
| **clearingagencycode** | `VARCHAR(10)` | 基金资金清算机构代码 |  |
| **investorsbirthday** | `VARCHAR(10)` | 投资人出生日期 |  |
| **defdividendmethod** | `VARCHAR(5)` | 默认分红方式 |  |
| **pagerno** | `VARCHAR(30)` | 投资人传呼机号码 |  |
| **certificatetype** | `VARCHAR(5)` | 证件类型 |  |
| **depositacct** | `VARCHAR(20)` | 投资人在销售人处用于交易的资金账号 |  |
| **regioncode** | `VARCHAR(5)` | 交易所在地区编号 |  |
| **transactioncfmdate** | `VARCHAR(10)` | 交易确认日期 |  |
| **educationlevel** | `VARCHAR(5)` | 投资人学历 |  |
| **emailaddress** | `VARCHAR(40)` | 投资人 E-MAIL 地址 |  |
| **faxno** | `VARCHAR(30)` | 投资人传真号码 |  |
| **freezingdeadline** | `VARCHAR(10)` | 冻结截止日期 |  |
| **frozencause** | `VARCHAR(5)` | 冻结原因 |  |
| **vocationcode** | `VARCHAR(5)` | 投资人职业代码 |  |
| **hometelno** | `VARCHAR(30)` | 投资人住址电话 |  |
| **certificateno** | `VARCHAR(30)` | 投资人证件号码 |  |
| **annualincome** | `NUMBER` | 投资人年收入 |  |
| **mobiletelno** | `VARCHAR(30)` | 投资人手机号码 |  |
| **multiacctflag** | `VARCHAR(5)` | 多渠道开户标志 |  |
| **investorname** | `VARCHAR(60)` | 投资人户名 |  |
| **branchcode** | `VARCHAR(10)` | 托管网点编号 |  |
| **officetelno** | `VARCHAR(30)` | 投资人单位电话号码 |  |
| **originalserialno** | `VARCHAR(20)` | 原 TA 确认流水号 |  |
| **originalappsheetno** | `VARCHAR(30)` | 原申请单编号 |  |
| **transactiondate** | `VARCHAR(10)` | 交易发生日期 |  |
| **transactiontime** | `VARCHAR(10)` | 交易发生时间 |  |
| **individualorinstitution** | `VARCHAR(5)` | 个人/机构标志 0-机构，1-个人 |  |
| **postcode** | `VARCHAR(10)` | 投资人邮政编码 |  |
| **transactorcertno** | `VARCHAR(20)` | 经办人证件号码 |  |
| **transactorcerttype** | `VARCHAR(5)` | 经办人证件类型 0-身份证，1-护照<br>2-军官证，3-士兵证<br>4-回乡证，5-户口本<br>6-外国护照，7-其它<br>8-无 |  |
| **transactorname** | `VARCHAR(20)` | 经办人姓名 |  |
| **returncode** | `VARCHAR(5)` | 交易处理返回代码 |  |
| **transactionaccountid** | `VARCHAR(20)` | 投资人交易账号 |  |
| **distributorcode** | `VARCHAR(5)` | 销售人代码 |  |
| **accountabbr** | `VARCHAR(20)` | 投资人户名简称 |  |
| **confdentialdocumentcode** | `VARCHAR(10)` | 密函编号 |  |
| **sex** | `VARCHAR(5)` | 投资人性别 0-女，1-男 |  |
| **shsecuritiesaccountid** | `VARCHAR(10)` | 上海证券账号 |  |
| **szsecuritiesaccountid** | `VARCHAR(10)` | 深圳证券账号 |  |
| **businesscode** | `VARCHAR(5)` | 业务代码 |  |
| **taaccountid** | `VARCHAR(15)` | 投资人基金账号 |  |
| **taserialno** | `VARCHAR(20)` | TA 确认流水号 |  |
| **telno** | `VARCHAR(25)` | 投资人电话号码 |  |
| **targettransactionaccountid** | `VARCHAR(10)` | 对方销售人处投资人交易账号 |  |
| **tradingmethod** | `VARCHAR(10)` | 使用的交易手段 |  |
| **minorflag** | `VARCHAR(5)` | 未成年人标志 0-否，1-是 |  |
| **minorid** | `VARCHAR(20)` | 未成年人 ID 号 |  |
| **delivertype** | `VARCHAR(5)` | 对帐单寄送选择 |  |
| **transactoridtype** | `VARCHAR(5)` | 经办人识别方式 |  |
| **accountcardid** | `VARCHAR(10)` | 基金帐户卡的凭证号 |  |
| **fromtaflag** | `VARCHAR(5)` | TA 发起业务标志 |  |
| **originalcfmdate** | `VARCHAR(10)` | TA 的原确认日期 |  |
| **deliverway** | `VARCHAR(10)` | 对帐单寄送方式 |  |
| **accountstatus** | `VARCHAR(5)` | 基金帐户状态 0-正常，1-冻结，2-挂失，<br>3-注销，4-挂帐，5-休眠 |  |
| **netno** | `VARCHAR(10)` | 操作网点编号 |  |
| **transactionaccountstatus** | `VARCHAR(5)` | 交易账户状态 0-正常，3-注销 |  |
| **vc_source** | `VARCHAR(20)` |  |  |
| **d_filedate** | `VARCHAR(20)` |  |  |
| **d_update** | `DATE` |  |  |