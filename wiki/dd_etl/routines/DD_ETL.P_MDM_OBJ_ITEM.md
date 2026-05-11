---
project: dd_etl
type: routine-note
status: active
created: 2026/05/11
updated: 2026/05/11
tags:
  - routine-note
related:
  - "[[tables/mdm_obj_item|mdm_obj_item]]"
  - "[[tables/mdm_object|mdm_object]]"
routine_type: PROCEDURE
---

# ⚙️ DD_ETL.P_MDM_OBJ_ITEM

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `PROCEDURE`
:::

---

## 🔗 相关表
- [mdm_obj_item](../tables/mdm_obj_item.md)
- [mdm_object](../tables/mdm_object.md)

---

## 📜 源码
```sql
PROCEDURE        P_MDM_OBJ_ITEM(I_STARTDATE in varchar2,
                                           I_ENDDATE   in varchar2,
                                           O_ERRCODE   OUT INTEGER,
                                           O_ERRMSG    OUT VARCHAR2) IS
  V_NUMBER NUMBER(10); --记录条数
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''YYYY-MM-DD''';
  O_ERRCODE := 0;
  O_ERRMSG  := '运行成功';
  --初始表
  insert into mdm_obj_item
    (f_item_id, f_obj_id, vc_item_name, vc_isused, d_updatetime)
    select SEQ_mdm_obj_item.Nextval,
           DD.F_OBJ_ID,
           D.COLUMN_NAME,
           '1',
           SYSDATE
      from dba_tab_cols d, mdm_object dd
     where d.owner = dd.vc_owner
       and d.table_name = dd.vc_obj_name
       and dd.vc_obj_type in ('VIEW', 'TABLE')
       AND NOT EXISTS (SELECT 1
              FROM mdm_obj_item ZZ
             WHERE ZZ.F_OBJ_ID = DD.F_OBJ_ID
               AND ZZ.VC_ITEM_NAME = D.COLUMN_NAME);
  UPDATE MDM_OBJ_ITEM T
     SET T.VC_ISUSED = '0'
   WHERE NOT EXISTS (SELECT 1
            FROM (SELECT DD.COLUMN_NAME, ZZ.F_OBJ_ID
                    FROM DBA_TAB_COLS DD, MDM_OBJECT ZZ
                   WHERE ZZ.VC_OBJ_NAME = DD.TABLE_NAME
                     AND ZZ.VC_OWNER = DD.OWNER) A
           WHERE A.COLUMN_NAME = T.VC_ITEM_NAME
             AND A.F_OBJ_ID = T.F_OBJ_ID);
  COMMIT;
  update mdm_obj_item t
     set t.vc_item_name_zh =
         (select d.comments
            from dba_col_comments d
           where d.owner = (select dd.vc_owner
                              from mdm_object dd
                             where dd.f_obj_id = t.f_obj_id)
             and d.column_name = t.vc_item_name
             and d.table_name =(select dd.vc_obj_name
                              from mdm_object dd
                             where dd.f_obj_id = t.f_obj_id)

             )
   where t.vc_isused = '1';
  commit;
  UPDATE MDM_OBJ_ITEM ZZ
     SET (zz.f_column_id,
          zz.vc_data_type,
          zz.f_data_length,
          zz.vc_null_able) =
         (select ee.COLUMN_ID, ee.DATA_TYPE, ee.DATA_LENGTH, ee.NULLABLE
            from dba_tab_columns ee,
                 (select tt.vc_owner,
                         tt.vc_obj_name,
                         dd.vc_item_name,
                         tt.f_obj_id
                    from mdm_object tt, mdm_obj_item dd
                   where tt.f_obj_id = dd.f_obj_id
                     and tt.vc_obj_type in ('TABLE', 'SYNONYM', 'VIEW')) ww
           where ee.OWNER = ww.vc_owner
             and ee.TABLE_NAME = ww.vc_obj_name
             and ee.COLUMN_NAME = ww.vc_item_name
             and ww.f_obj_id = zz.f_obj_id
             and ww.vc_item_name = zz.vc_item_name)
   where zz.vc_isused = '1';
  commit;
EXCEPTION
  WHEN OTHERS THEN
    O_ERRCODE := SQLCODE;
    O_ERRMSG  := SUBSTR('未处理异常:' || SQLERRM || '。' ||
                        DBMS_UTILITY.FORMAT_ERROR_BACKTRACE,
                        1,
                        1000);

END P_MDM_OBJ_ITEM;
```