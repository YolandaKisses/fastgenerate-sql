---
project: dd_etl
type: routine-note
status: active
created: 2026/05/11
updated: 2026/05/11
tags:
  - routine-note
related:
  - "[[tables/temp_mdm_source_procedurce|temp_mdm_source_procedurce]]"
routine_type: FUNCTION
---

# ⚙️ DD_ETL.FUN_MDM_CONNECT

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `FUNCTION`
:::

---

## 🔗 相关表
- [temp_mdm_source_procedurce](../tables/temp_mdm_source_procedurce.md)

---

## 📜 源码
```sql
function fun_mdm_connect(vc_owner    in varchar2,
                                        vc_obj_name in varchar2) return clob IS
  retn clob; --记录条数
BEGIN
       for cc in (select d.text from dba_source d,TEMP_MDM_SOURCE_PROCEDURCE dd where d.owner=vc_owner
              and d.owner=dd.owner
              and d.name=dd.name
              and d.type=dd.type
              and d.line between dd.line and dd.maxline
              and dd.name||'.'||dd.procedure_name=vc_obj_name
              order by d.line
       )loop
            retn :=retn||' '||cc.text;
       end loop;
return retn;
END fun_mdm_connect;
```