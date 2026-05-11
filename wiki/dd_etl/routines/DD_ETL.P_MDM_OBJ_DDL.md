---
project: dd_etl
type: routine-note
status: active
created: 2026/05/11
updated: 2026/05/11
tags:
  - routine-note
related:
  - "[[tables/mdm_obj_ddl|mdm_obj_ddl]]"
  - "[[tables/mdm_object|mdm_object]]"
routine_type: PROCEDURE
---

# ⚙️ DD_ETL.P_MDM_OBJ_DDL

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `PROCEDURE`
:::

---

## 🔗 相关表
- [mdm_obj_ddl](../tables/mdm_obj_ddl.md)
- [mdm_object](../tables/mdm_object.md)

---

## 📜 源码
```sql
PROCEDURE        P_MDM_OBJ_DDL(I_STARTDATE in varchar2,
                                          I_ENDDATE   in varchar2,
                                          O_ERRCODE   OUT INTEGER,
                                          O_ERRMSG    OUT VARCHAR2)  AUTHID  CURRENT_USER IS
  /*
              依赖TEMP_MDM_SOURCE_PROCEDURCE
  */
  V_NUMBER NUMBER(10); --记录条数
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''YYYY-MM-DD''';
  O_ERRCODE := 0;
  O_ERRMSG  := '运行成功';
  --初始表
  insert into mdm_obj_ddl
    (f_obj_id, vc_ddl,d_updatetime)
    select T.F_OBJ_ID,
           dbms_metadata.get_ddl(T.VC_OBJ_TYPE, T.VC_OBJ_NAME, T.VC_OWNER),
           sysdate
      from mdm_object t
     where t.vc_obj_type = 'TABLE'
       AND T.VC_ISUSED = '1'
       AND NOT EXISTS (SELECT 1 FROM MDM_OBJ_DDL ZZ WHERE ZZ.F_OBJ_ID=T.F_OBJ_ID);
  COMMIT;
  insert into mdm_obj_ddl
    (f_obj_id, vc_ddl,d_updatetime)
    select T.F_OBJ_ID,
           dbms_metadata.get_ddl(T.VC_OBJ_TYPE, T.VC_OBJ_NAME, T.VC_OWNER),
           sysdate
      from mdm_object t
     where t.vc_obj_type = 'SYNONYM'
       AND T.VC_ISUSED = '1'
       AND NOT EXISTS (SELECT 1 FROM MDM_OBJ_DDL ZZ WHERE ZZ.F_OBJ_ID=T.F_OBJ_ID);
  COMMIT;
  insert into mdm_obj_ddl
    (f_obj_id, vc_ddl,d_updatetime)
    select T.F_OBJ_ID,
           dbms_metadata.get_ddl(T.VC_OBJ_TYPE, T.VC_OBJ_NAME, T.VC_OWNER),
           sysdate
      from mdm_object t
     where t.vc_obj_type = 'VIEW'
       AND T.VC_ISUSED = '1'
       AND NOT EXISTS (SELECT 1 FROM MDM_OBJ_DDL ZZ WHERE ZZ.F_OBJ_ID=T.F_OBJ_ID);
  COMMIT;
  insert into mdm_obj_ddl
    (f_obj_id, vc_ddl,d_updatetime)
    select T.F_OBJ_ID,
           dbms_metadata.get_ddl((SELECT D.OBJECT_TYPE
                                   FROM Dba_Objects D
                                  WHERE T.VC_OWNER = D.OWNER
                                    AND T.VC_OBJ_NAME = D.OBJECT_NAME
                                    AND D.OBJECT_TYPE IN
                                        ('FUNCTION', 'PROCEDURE')
                                    AND ROWNUM <= 1),
                                 T.VC_OBJ_NAME,
                                 T.VC_OWNER),
                                 sysdate
      from mdm_object t
     where EXISTS (SELECT 1
              FROM Dba_Objects D
             WHERE T.VC_OWNER = D.OWNER
               AND T.VC_OBJ_NAME = D.OBJECT_NAME
               AND D.OBJECT_TYPE IN ('FUNCTION', 'PROCEDURE'))
       AND T.VC_ISUSED = '1'
       AND NOT EXISTS (SELECT 1 FROM MDM_OBJ_DDL ZZ WHERE ZZ.F_OBJ_ID=T.F_OBJ_ID);
  COMMIT;
  insert into mdm_obj_ddl
    (f_obj_id, vc_ddl,d_updatetime)
    select t.f_obj_id, fun_mdm_connect(t.vc_owner, t.vc_obj_name),sysdate
      from mdm_object t
     where t.vc_obj_type = 'PROCEDURE'
       AND T.VC_ISUSED = '1'
       and nvl(regexp_substr(upper(t.vc_obj_name),'\.+?'),'0')<>'0'
       AND NOT EXISTS (SELECT 1 FROM MDM_OBJ_DDL ZZ WHERE ZZ.F_OBJ_ID=T.F_OBJ_ID);
  COMMIT;
EXCEPTION
  WHEN OTHERS THEN
    O_ERRCODE := SQLCODE;
    O_ERRMSG  := SUBSTR('未处理异常:' || SQLERRM || '。' ||
                        DBMS_UTILITY.FORMAT_ERROR_BACKTRACE,
                        1,
                        1000);

END P_MDM_OBJ_DDL;
```