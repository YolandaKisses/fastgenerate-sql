---
project: dd_etl
type: routine-note
status: active
created: 2026/05/11
updated: 2026/05/11
tags:
  - routine-note
related:
  - "[[tables/mdm_object|mdm_object]]"
  - "[[tables/mdm_proc_table|mdm_proc_table]]"
  - "[[tables/mdm_proc_table_physics|mdm_proc_table_physics]]"
routine_type: PROCEDURE
---

# ⚙️ DD_ETL.P_MDM_PROC_TABLE_PHYSICS

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `PROCEDURE`
:::

---

## 🔗 相关表
- [mdm_object](../tables/mdm_object.md)
- [mdm_proc_table](../tables/mdm_proc_table.md)
- [mdm_proc_table_physics](../tables/mdm_proc_table_physics.md)

---

## 📜 源码
```sql
PROCEDURE        P_MDM_PROC_TABLE_PHYSICS(I_STARTDATE in varchar2,
                                            I_ENDDATE   in varchar2,
                                            O_ERRCODE   OUT INTEGER,
                                            O_ERRMSG    OUT VARCHAR2) IS
  V_NUMBER NUMBER(10); --记录条数
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''YYYY-MM-DD''';
  O_ERRCODE := 0;
  O_ERRMSG  := '运行成功';
delete from mdm_proc_table_physics;
commit;
insert into mdm_proc_table_physics
  (F_PROC_ID, F_TABLE_ID, VC_ISAUTO, D_UPDATETIME)
  select F_PROC_ID, F_TABLE_ID, VC_ISAUTO, D_UPDATETIME
     from mdm_proc_table;
update mdm_proc_table_physics t
   set t.f_table_id = NVL((SELECT DD.F_OBJ_ID
                            FROM MDM_OBJECT DD
                           WHERE DD.VC_OWNER =
                                 (SELECT ZZ.VC_DEPENDENCIES_OWNER
                                    FROM MDM_OBJECT ZZ
                                   WHERE ZZ.F_OBJ_ID = T.F_TABLE_ID)
                             AND DD.VC_OBJ_NAME =
                                 (SELECT ZZ.VC_DEPENDENCIES_TABLE_NAME
                                    FROM MDM_OBJECT ZZ
                                   WHERE ZZ.F_OBJ_ID = T.F_TABLE_ID)),
                          f_table_id)
 where exists (select 1
          from mdm_object d
         where d.f_obj_id = t.f_table_id
           and d.vc_obj_type = 'SYNONYM');
commit;
EXCEPTION
  WHEN OTHERS THEN
    O_ERRCODE := SQLCODE;
    O_ERRMSG  := SUBSTR('未处理异常:' || SQLERRM || '。' ||
                        DBMS_UTILITY.FORMAT_ERROR_BACKTRACE,
                        1,
                        1000);

END P_MDM_PROC_TABLE_PHYSICS;
```