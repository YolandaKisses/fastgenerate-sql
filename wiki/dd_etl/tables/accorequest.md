---
summary: 账户确认信息表，存储账户相关请求的确认数据。
table_type: 流水表
tags:
  - db-table
  - 账户
  - 确认
  - 投资人
  - 基金
  - 交易
related:
  - "[[acco]]"
  - "[[accountinfo_zs]]"
keywords:
  - 账户确认
  - 基金帐号
  - 交易确认
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
  - accorequest
  - acco
  - accountinfo_zs
review_status: unreviewed
---

# 🏷️ accorequest

[⬅️ 返回数据源总览](../index.md)

::: tip 概述
- **数据源**: `dd_etl`
- **业务说明**: 记录账户确认请求及处理结果，包括投资人信息、交易信息及确认状态等。
:::

---

## 🔗 表间关系
::: info 关联模型与推断
- 与acco表（客户基本信息）通过taaccountid（投资人基金帐号）关联，置信度：高。
- 与accountinfo_zs表（帐户资料52）通过taaccountid或transactionaccountid关联，置信度：中。

- [acco](./acco.md) · has · `未提供` · 置信度：`高` · 依据：未提供
- [accountinfo_zs](./accountinfo_zs.md) · related_to · `未提供` · 置信度：`中` · 依据：未提供

---

## 💡 核心字段解读
> [!quote] 业务逻辑说明
> - businesscode: 业务代码
> - transactiondate: 交易发生日期（数值型）
> - appsheetserialno: 申请单编号
> - distributorcode: 销售商代码
> - taaccountid: 投资人基金帐号
> - investorname: 投资人户名
> - certificatetype: 个人证件类型及机构证件型
> - certificateno: 投资人证件号码
> - transactionaccountid: 投资人基金交易帐号
> - accounttype: 账户分红方式（原账户类型）
> - transactioncfmdate: 交易确认日期（数值型）
> - returncode: 交易处理返回代码
> - errordetail: 出错详细信息
> - referrertype: 推荐人类型，枚举值：1-内部员工；2-注册用户；3-基金账户；4-客户经理编号；5-客户经理姓名；0-其他
> - acceptancemode: 受理方式，枚举值：0-柜台；1-电话；2-网上；3-自助；4-传真；5-其他
> - isyuebao: 余额宝交易标志，1-是；0或空-否
> - orgniztiontype: 机构类型，枚举值：0-保险公司；1-基金管理公司；3-信托公司；4-证券公司；8-其他；9-银行；A-私募基金管理人等
> - customerrisklevel: 客户风险等级，枚举值：0-无风险；1-低风险；2-中低风险；3-中等风险；4-中高风险；5-高风险

---

## ⚠️ 注意事项
::: warning 风险提示
字段备注中部分枚举值由分号或冒号分隔，已按原样整理
:::

---

## 🛠️ 相关存储过程

### 🔍 命中列表
*暂无命中过程*

---

## 📋 字段明细

| 字段名 | 类型 | 原始备注 | 补充备注 |
| :--- | :--- | :--- | :--- |
| **businesscode** | `NUMBER` | 业务代码 |  |
| **transactiondate** | `NUMBER` | 交易发生日期 |  |
| **transactiontime** | `NUMBER` | 交易发生时间 |  |
| **appsheetserialno** | `VARCHAR(30)` | 申请单编号 |  |
| **distributorcode** | `VARCHAR(10)` | 销售商代码 |  |
| **regioncode** | `VARCHAR(10)` | 交易所在地区编号 |  |
| **branchcode** | `VARCHAR(20)` | 托管网点号码 |  |
| **taaccountid** | `VARCHAR(20)` | 投资人基金帐号 |  |
| **investorname** | `VARCHAR(100)` | 投资人户名 |  |
| **accountabbr** | `VARCHAR(20)` | 投资人户名简称 |  |
| **individualorinstitution** | `VARCHAR(5)` | 个人/机构标志 |  |
| **certificatetype** | `VARCHAR(5)` | 个人证件类型及机构证件型 |  |
| **certificateno** | `VARCHAR(50)` | 投资人证件号码 |  |
| **instreprname** | `VARCHAR(50)` | 法人代表姓名 |  |
| **transactorname** | `VARCHAR(50)` | 经办人姓名 |  |
| **transactorcerttype** | `VARCHAR(50)` | 经办人证件类型 |  |
| **transactorcertno** | `VARCHAR(20)` | 经办人证件号码 |  |
| **address** | `VARCHAR(80)` | 通讯地址 |  |
| **postcode** | `VARCHAR(10)` | 投资人邮政编码 |  |
| **telno** | `VARCHAR(30)` | 投资人电话号码 |  |
| **faxno** | `VARCHAR(30)` | 投资人传真号码 |  |
| **emailaddress** | `VARCHAR(50)` | 投资人E-MAIL地址 |  |
| **mobiletelno** | `VARCHAR(50)` | 投资人手机号码 |  |
| **investorsbirthday** | `VARCHAR(10)` | 投资人出生日期 |  |
| **sex** | `VARCHAR(5)` | 投资人性别 |  |
| **educationlevel** | `VARCHAR(5)` | 投资人学历 |  |
| **vocationcode** | `VARCHAR(5)` | 投资人职业代码 |  |
| **annualincome** | `VARCHAR(10)` | 投资人年收入 |  |
| **transactionaccountid** | `VARCHAR(20)` | 投资人基金交易帐号 |  |
| **confdentialdocumentcode** | `VARCHAR(10)` | 密函编号 |  |
| **shsecuritiesaccountid** | `VARCHAR(20)` | 上交所证券帐号 |  |
| **szsecuritiesaccountid** | `VARCHAR(20)` | 深交所证券帐号 |  |
| **callcenter** | `VARCHAR(5)` | CALL CENTER交易 |  |
| **internet** | `VARCHAR(5)` | INTERNET交易 |  |
| **selfhelp** | `VARCHAR(5)` | 自助终端 |  |
| **delivertype** | `VARCHAR(5)` | 对帐单寄送选择 |  |
| **freezingdeadline** | `VARCHAR(10)` | 冻结截止日期 |  |
| **frozencause** | `VARCHAR(5)` | 冻结原因 |  |
| **originalappsheetno** | `VARCHAR(50)` | 原申请单编号 |  |
| **acctname** | `VARCHAR(100)` | 投资人收款银行账户户名 |  |
| **acctno** | `VARCHAR(60)` | 投资人收款银行账户帐号 |  |
| **clearingagencycode** | `VARCHAR(10)` | 投资人收款银行账户开户行 |  |
| **nationality** | `VARCHAR(10)` | 投资者国籍 |  |
| **accounttype** | `VARCHAR(5)` | 账户分红方式(原账户类型) |  |
| **netno** | `VARCHAR(10)` | 操作网点编号 |  |
| **transactioncfmdate** | `NUMBER` | 交易确认日期 |  |
| **taserialno** | `VARCHAR(60)` | TA确认编号 |  |
| **unfrozenbalance** | `VARCHAR(20)` | 解冻红利金额 |  |
| **returncode** | `NUMBER` | 交易处理返回代码 |  |
| **errordetail** | `VARCHAR(60)` | 出错详细信息 |  |
| **vc_source** | `VARCHAR(20)` |  |  |
| **d_filedate** | `VARCHAR(20)` |  |  |
| **d_update** | `DATE` |  |  |
| **worktel** | `VARCHAR(22)` | 工作单位电话 |  |
| **organization** | `VARCHAR(40)` | 工作单位名称 |  |
| **specialcode** | `VARCHAR(20)` | 特殊代码 |  |
| **tainterbusinesscode** | `VARCHAR(5)` | TA内部业务代码 |  |
| **referrer** | `VARCHAR(40)` | 推荐人 |  |
| **referrertype** | `VARCHAR(2)` | 推荐人类型 1:内部员工<br>2:注册用户<br>3:基金账户<br>4:客户经理编号<br>5:客户经理姓名<br>0:其他<br> |  |
| **validityofcertificate** | `VARCHAR(16)` | 证件有效期 |  |
| **counterpartyaccountno** | `VARCHAR(40)` | 对方交易账号 |  |
| **acceptancemode** | `VARCHAR(2)` | 受理方式 0-柜台 1-电话 2-网上 3-自助 4-传真 5-其他<br> |  |
| **isyuebao** | `VARCHAR(2)` | 余额宝交易标志<br>1：是；0或空否<br> |  |
| **orgniztiontype** | `VARCHAR(2)` | 机构类型 0-保险公司，1-基金管理公司，3-信托公司，4-证券公司，8-其他，9-银行；A:私募基金管理人；B:期货公司；C-基金管理公司子公司；D-证券公司子公司；E-期货公司子公司；F-财务公司；G:其他境内金融机构；H:机关法人；I:事业单位法人；J:社会团体法人；K:非金融机构企业法人；L:非金融类非法人机构；M:境外代理人；N:境外金融机构； P:外国战略投资者；Q:境外非金融机构。<br> |  |
| **customerrisklevel** | `VARCHAR(1)` | 客户风险等级<br> 0-无风险 1-低风险 2-中低风险 3-中等风险 4-中高风险 5-高风险<br> |  |
| **cechanneling** | `VARCHAR(120)` | 电商渠道 |  |
| **remarks** | `VARCHAR(500)` | 备注 |  |
| **agent** | `VARCHAR(20)` | 经纪人 |  |