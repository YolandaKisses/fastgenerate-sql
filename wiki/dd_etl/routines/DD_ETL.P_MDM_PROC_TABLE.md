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
  - "[[tables/temp_mdm_proc_table|temp_mdm_proc_table]]"
routine_type: PROCEDURE
---

# ⚙️ DD_ETL.P_MDM_PROC_TABLE

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `PROCEDURE`
:::

---

## 🔗 相关表
- [mdm_object](../tables/mdm_object.md)
- [mdm_proc_table](../tables/mdm_proc_table.md)
- [temp_mdm_proc_table](../tables/temp_mdm_proc_table.md)

---

## 📜 源码
```sql
PROCEDURE        P_MDM_PROC_TABLE(I_STARTDATE in varchar2,
                                             I_ENDDATE   in varchar2,
                                             O_ERRCODE   OUT INTEGER,
                                             O_ERRMSG    OUT VARCHAR2) IS
  V_NUMBER NUMBER(10); --记录条数,目前表的来自哪些存储过程只针对本用户下进行搜索，剔除函数
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''YYYY-MM-DD''';
  O_ERRCODE := 0;
  O_ERRMSG  := '运行成功';
  execute IMMEDIATE 'TRUNCATE TABLE TEMP_PROC_TABLE';
  INSERT INTO TEMP_MDM_PROC_TABLE
    (F_PROC_ID, F_TABLE_ID)
    select (SELECT D.F_OBJ_ID
              FROM MDM_OBJECT D
             WHERE D.VC_OBJ_NAME = T.name
               AND T.owner = D.VC_OWNER),
           (SELECT D.F_OBJ_ID
              FROM MDM_OBJECT D
             WHERE D.VC_OBJ_NAME = T.referenced_name
               AND T.referenced_owner = D.VC_OWNER)
      from dba_dependencies t, MDM_OBJECT ZZ
     where t.name = ZZ.VC_OBJ_NAME
       AND ZZ.VC_OBJ_TYPE = 'PROCEDURE'
       AND T.owner = ZZ.VC_OWNER
       AND EXISTS (SELECT 1
              FROM MDM_OBJECT DD
             WHERE DD.VC_OBJ_NAME = T.referenced_name
               AND DD.VC_OWNER = T.referenced_owner)
       and not exists (select 1
              from mdm_proc_table ddd
             where ddd.F_TABLE_ID =
                   (SELECT D.F_OBJ_ID
                      FROM MDM_OBJECT D
                     WHERE D.VC_OBJ_NAME = T.referenced_name
                       AND T.referenced_owner = D.VC_OWNER)
               and ddd.F_PROC_ID =
                   (SELECT D.F_OBJ_ID
                      FROM MDM_OBJECT D
                     WHERE D.VC_OBJ_NAME = T.name
                       AND T.owner = D.VC_OWNER));
  commit;
  INSERT INTO MDM_PROC_TABLE t
    (F_PROC_ID, F_TABLE_ID, VC_ISAUTO, D_UPDATETIME)
    select f_proc_id, f_table_id, '1', sysdate
      from temp_MDM_proc_table s
     where not exists (select 1
              from mdm_proc_table zz
             where zz.f_proc_id = s.f_proc_id
               and zz.f_table_id = s.f_table_id);
  COMMIT;
  UPDATE MDM_PROC_TABLE s
     SET s.VC_ISAUTO = '0'
   WHERE NOT EXISTS (SELECT 1 from temp_MDM_proc_table zz where zz.f_proc_id = s.f_proc_id
               and zz.f_table_id = s.f_table_id)
           ;
  COMMIT;
EXCEPTION
  WHEN OTHERS THEN
    O_ERRCODE := SQLCODE;
    O_ERRMSG  := SUBSTR('未处理异常:' || SQLERRM || '。' ||
                        DBMS_UTILITY.FORMAT_ERROR_BACKTRACE,
                        1,
                        1000);

END P_MDM_PROC_TABLE;
```