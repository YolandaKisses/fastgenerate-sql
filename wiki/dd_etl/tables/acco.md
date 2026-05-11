---
summary: 客户基本信息核心表，覆盖个人/机构客户的身份、联系方式、账户状态、风险等级等关键属性。
table_type: 事实表
tags:
  - db-table
  - 客户信息
  - 账户管理
  - 投资人
  - 风险等级
related:
  - "[[accorequest]]"
  - "[[accountinfo_zs]]"
keywords:
  - 客户号
  - 基金帐号
  - 证件类型
  - 风险等级
  - 账户状态
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
  - acco
  - accorequest
  - accountinfo_zs
review_status: unreviewed
---

# 🏷️ acco

[⬅️ 返回数据源总览](../index.md)

::: tip 概述
- **数据源**: `dd_etl`
- **业务说明**: 存储客户基本信息和账户资料，包括投资人身份、联系方式、风险等级、账户状态等，用于客户管理和账户维护。
:::

---

## 🔗 表间关系
::: info 关联模型与推断
- 重要关联表：accorequest（账户确认信息）- 通过 customerid 关联，置信度：高
- accountinfo_zs（帐户资料52）- 通过 customerid 或 taaccountid 关联，置信度：中

- [accorequest](./accorequest.md) · 客户基本信息-账户确认信息 · `未提供` · 置信度：`高` · 依据：未提供
- [accountinfo_zs](./accountinfo_zs.md) · 客户基本信息-帐户资料 · `未提供` · 置信度：`中` · 依据：未提供

---

## 💡 核心字段解读
> [!quote] 业务逻辑说明
> - customerid: 客户号，唯一标识投资人
> - investorname: 投资人姓名全称
> - taaccountid: 投资人基金帐号
> - accountstatus: 帐户状态，枚举值 N-正常、F-冻结、T-注销
> - customerrisklevel: 客户风险等级，0-无风险、1-低风险、2-中低风险、3-中等风险、4-中高风险、5-高风险
> - billsendingway: 对账单寄送途径，1-邮寄、2-Email、3-短信、4-传真
> - orgniztiontype: 机构类型，0-保险公司、1-基金管理公司、3-信托公司、4-证券公司、8-其他、9-银行等
> - certificatetype: 投资人证件类型
> - certificateno: 投资人证件号码
> - distributorcode: 销售公司代码
> - regioncode: 开户地区编号
> - branchcode: 开户网点号码
> - accountopeningdate: 帐户开通日期
> - firstinvestmentdate: 首次投资日期
> - freezingdeadline: 冻结截止日期
> - frozencause: 冻结原因

---

## ⚠️ 注意事项
::: warning 风险提示
- 部分字段如 vc_source、d_filedate、d_update 无备注，可能是ETL标记字段
- accountstatus、billsendingway、orgniztiontype 等存在枚举值，需按业务字典解析
:::

---

## 🛠️ 相关存储过程

### 🔍 命中列表
*暂无命中过程*

---

## 📋 字段明细

| 字段名 | 类型 | 原始备注 | 补充备注 |
| :--- | :--- | :--- | :--- |
| **recordflag** | `VARCHAR(10)` | 记录内容标志 |  |
| **customerid** | `VARCHAR(20)` | 客户号 |  |
| **individualorinstitution** | `VARCHAR(5)` | 个人/机构标志 |  |
| **certificatetype** | `VARCHAR(10)` | 投资人证件类型 |  |
| **certificateno** | `VARCHAR(30)` | 投资人证件号码 |  |
| **taaccountid** | `VARCHAR(20)` | 投资人基金帐号 |  |
| **taaccounttype** | `VARCHAR(5)` | 基金帐号类型 |  |
| **distributorcode** | `VARCHAR(5)` | 销售公司代码 |  |
| **regioncode** | `VARCHAR(5)` | 开户地区编号 |  |
| **branchcode** | `VARCHAR(10)` | 开户网点号码 |  |
| **investorname** | `VARCHAR(100)` | 投资人姓名全称 |  |
| **accountabbr** | `VARCHAR(80)` | 投资人姓名简称 |  |
| **nationality** | `VARCHAR(10)` | 国籍 |  |
| **instreprname** | `VARCHAR(20)` | 法人代表姓名 |  |
| **transactorname** | `VARCHAR(40)` | 经办人姓名 |  |
| **transactorcerttype** | `VARCHAR(5)` | 经办人证件类型 |  |
| **transactorcertno** | `VARCHAR(20)` | 经办人证件号码 |  |
| **address** | `VARCHAR(100)` | 通讯地址 |  |
| **postcode** | `VARCHAR(10)` | 邮政编码 |  |
| **telno** | `VARCHAR(20)` | 投资人电话号码 |  |
| **faxno** | `VARCHAR(20)` | 投资人传真号码 |  |
| **emailaddress** | `VARCHAR(40)` | 投资人E-MAIL地址 |  |
| **mobiletelno** | `VARCHAR(40)` | 投资人手机号码 |  |
| **bpno** | `VARCHAR(20)` | 投资人呼机号码 |  |
| **investorsbirthday** | `VARCHAR(10)` | 投资人出生日期 |  |
| **sex** | `VARCHAR(5)` | 投资人性别 |  |
| **educationlevel** | `VARCHAR(10)` | 投资人学历 |  |
| **familyscale** | `VARCHAR(5)` | 家庭人口数 |  |
| **vocationcode** | `VARCHAR(5)` | 投资人职业代码 |  |
| **annualincome** | `VARCHAR(10)` | 投资人年收入 |  |
| **callcenter** | `VARCHAR(5)` | Call Center交易 |  |
| **internet** | `VARCHAR(5)` | 网上交易 |  |
| **selfhelp** | `VARCHAR(5)` | 自助终端交易 |  |
| **delivertype** | `VARCHAR(5)` | 对帐单寄送选择 |  |
| **confirmmailtype** | `VARCHAR(5)` | 交易确认书寄送选择 |  |
| **freezingdeadline** | `VARCHAR(10)` | 冻结截止日期 |  |
| **frozencause** | `VARCHAR(5)` | 冻结原因 |  |
| **acctname** | `VARCHAR(100)` | 投资人收款银行账户户名 |  |
| **acctno** | `VARCHAR(50)` | 投资人收款银行账户帐号 |  |
| **clearingagencycode** | `VARCHAR(20)` | 投资人收款银行账户开户行 |  |
| **vc_source** | `VARCHAR(20)` |  |  |
| **d_filedate** | `VARCHAR(20)` |  |  |
| **d_update** | `DATE` |  |  |
| **accountopeningdate** | `VARCHAR(10)` | 帐户开通日期 |  |
| **lastmodifieddate** | `VARCHAR(10)` | 最后修改日期<br> |  |
| **accountstatus** | `VARCHAR(4)` | 帐户状态 N：正常； F：冻结；T：注销；<br> |  |
| **firstinvestmentdate** | `VARCHAR(10)` | 首次投资日期 |  |
| **conversiontimes** | `VARCHAR(10)` | 一年内基金转换次数 |  |
| **agent** | `VARCHAR(20)` | 经纪人 |  |
| **billsendingway** | `VARCHAR(2)` | 对账单寄送途径 1-邮寄，2-Email，3-短信,4-传真<br> |  |
| **remarks** | `VARCHAR(100)` | 备注<br> |  |
| **worktel** | `VARCHAR(25)` | 工作单位电话<br> |  |
| **organization** | `VARCHAR(40)` | 工作单位名称 |  |
| **specialcode** | `VARCHAR(20)` | 特殊代码 |  |
| **activitycode** | `VARCHAR(5)` | 活动代码 |  |
| **password** | `VARCHAR(40)` | 密码 |  |
| **referrer** | `VARCHAR(40)` | 推荐人 |  |
| **actionnetwork** | `VARCHAR(10)` | 操作网点 |  |
| **referrertype** | `VARCHAR(2)` | 推荐人类型 1:内部员工<br>2:注册用户<br>3:基金账户<br>4:客户经理编号<br>5:客户经理姓名<br>0:其他 |  |
| **validityofcertificate** | `VARCHAR(16)` | 证件有效期 |  |
| **orgniztiontype** | `VARCHAR(2)` | 机构类型 0-保险公司，1-基金管理公司，3-信托公司，4-证券公司，8-其他，9-银行；A:私募基金管理人；B:期货公司；C-基金管理公司子公司；D-证券公司子公司；E-期货公司子公司；F-财务公司；G:其他境内金融机构；H:机关法人；I:事业单位法人；J:社会团体法人；K:非金融机构企业法人；L:非金融类非法人机构；M:境外代理人；N:境外金融机构； P:外国战略投资者；Q:境外非金融机构。 |  |
| **customerrisklevel** | `VARCHAR(2)` | 客户风险等级<br> 0-无风险 1-低风险 2-中低风险 3-中等风险 4-中高风险 5-高风险 |  |
| **instrepridtype** | `VARCHAR(2)` | 法人证件类型 0-身份证，1-护照，2-军官证，3-士兵证，4-港澳居民来往内地通行证，5-户口本，6-外国护照，7-其他，8-文职证，9-警官证，A-台胞证,B-外国人永久居留证<br> |  |
| **instrepridno** | `VARCHAR(30)` | 法人证件号码 |  |