---
project: dd_etl
type: routine-note
status: active
created: 2026/05/11
updated: 2026/05/11
tags:
  - routine-note
related:
routine_type: FUNCTION
---

# ⚙️ DD_ETL.RUN

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `FUNCTION`
:::

---

## 🔗 相关表
*暂无*

---

## 📜 源码
```sql
function run(methodName varchar2,params varchar2,encoding varchar2) return varchar2 as language java name 'Shell.run(java.lang.String,java.lang.String,java.lang.String) return java.lang.String';
```