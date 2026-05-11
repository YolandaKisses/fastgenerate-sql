---
project: dd_etl
type: routine-note
status: active
created: 2026/05/11
updated: 2026/05/11
tags:
  - routine-note
related:
routine_type: PROCEDURE
---

# ⚙️ DD_ETL.P_TEST_PROC_AUTO

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `PROCEDURE`
:::

---

## 🔗 相关表
*暂无*

---

## 📜 源码
```sql
PROCEDURE P_TEST_PROC_AUTO IS
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''YYYY-MM-DD''';


  insert into test_xulei_acc(vc_name, f_age, d_date, vc_fundcode)
  values('xxx',12,DATE'2018-01-01','aaa');


END P_TEST_PROC_AUTO;
```