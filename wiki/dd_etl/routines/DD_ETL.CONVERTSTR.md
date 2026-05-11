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

# ⚙️ DD_ETL.CONVERTSTR

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
function convertStr(str in varchar2
) return  varchar2
as
tmp varchar2(50);
begin
  tmp:=CONVERT(utl_raw.cast_to_varchar2(str),'ZHS16GBK','UTF8');
  
  return tmp;
  end;
```