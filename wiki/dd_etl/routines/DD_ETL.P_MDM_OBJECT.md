---
project: dd_etl
type: routine-note
status: active
created: 2026/05/11
updated: 2026/05/11
tags:
  - routine-note
related:
  - "[[tables/mdm_obj_group|mdm_obj_group]]"
  - "[[tables/mdm_object|mdm_object]]"
routine_type: PROCEDURE
---

# ⚙️ DD_ETL.P_MDM_OBJECT

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `PROCEDURE`
:::

---

## 🔗 相关表
- [mdm_obj_group](../tables/mdm_obj_group.md)
- [mdm_object](../tables/mdm_object.md)

---

## 📜 源码
```sql
PROCEDURE        P_MDM_OBJECT(I_STARTDATE in varchar2,
                                         I_ENDDATE   in varchar2,
                                         O_ERRCODE   OUT INTEGER,
                                         O_ERRMSG    OUT VARCHAR2) IS
  V_NUMBER NUMBER(10); --记录条数
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''YYYY-MM-DD''';
  O_ERRCODE := 0;
  O_ERRMSG  := '运行成功';
  --初始表
  insert into mdm_object
    (f_obj_id, vc_owner, vc_obj_name, vc_obj_type, vc_isused, d_updatetime)
    select seq_mdm_object.nextval,
           tt.VC_owner,
           d.table_name,
           'TABLE',
           '1',
           SYSDATE
      from dba_tables d, mdm_owner tt

     where d.owner = tt.VC_owner
       and not exists (select 1
              from mdm_object zz
             where zz.vc_owner = tt.vc_owner
               and d.table_name = zz.vc_obj_name);
  --更新使用状态
  update mdm_object t
     set t.vc_isused = '0'
   where t.vc_obj_type = 'TABLE'
     AND NOT EXISTS (SELECT 1
            FROM DBA_TABLES ZZ
           WHERE ZZ.OWNER = T.VC_OWNER
             AND ZZ.TABLE_NAME = T.VC_OBJ_NAME);
  --先根据前缀划分，最后在根据后缀划分。
  --更新分组id号
  update mdm_object t
     set t.f_group_id =
         (select ZZ.F_GROUP_ID
            from mdm_obj_group zz
           where zz.vc_owner = t.vc_owner
             and zz.vc_group_code =
                 substr(t.vc_obj_name, 0, length(zz.vc_group_code))
                 and zz.vc_group_type='PRE')
   where t.vc_obj_type = 'TABLE'
   and exists( select 1
            from mdm_obj_group zz
           where zz.vc_owner = t.vc_owner
             and zz.vc_group_code =
                 substr(t.vc_obj_name, 0, length(zz.vc_group_code))
                 and zz.vc_group_type='PRE');

  --根据后缀划分
  update mdm_object t
     set t.f_group_id =
         (select ZZ.F_GROUP_ID
            from mdm_obj_group zz
           where zz.vc_owner = t.vc_owner
             and zz.vc_group_code =
                 substr(t.vc_obj_name,-length(zz.vc_group_code))
                 and zz.vc_group_type='END')
   where t.vc_obj_type = 'TABLE'
   and exists( select 1
            from mdm_obj_group zz
           where zz.vc_owner = t.vc_owner
             and zz.vc_group_code =
                  substr(t.vc_obj_name,-length(zz.vc_group_code))
                 and zz.vc_group_type='END');
    --根据自定义规则
  update mdm_object t
     set t.f_group_id =
         (select ZZ.F_GROUP_ID
            from mdm_obj_group zz
           where zz.vc_owner = t.vc_owner
             and t.vc_obj_name like zz.vc_group_code
                 and zz.vc_group_type='CUSTOM')
   where t.vc_obj_type = 'TABLE'
   and exists( select 1
            from mdm_obj_group zz
           where zz.vc_owner = t.vc_owner
           and t.vc_obj_name like zz.vc_group_code
           and zz.vc_group_type='CUSTOM');


  --根据名称自定义
  update mdm_object t
     set t.f_group_id =
         (select ZZ.F_GROUP_ID
            from mdm_obj_group zz
           where zz.vc_owner = t.vc_owner
             and t.vc_obj_name_zh like zz.vc_group_code
                 and zz.vc_group_type='CUSTOM')
   where t.vc_obj_type = 'TABLE'
   and exists( select 1
            from mdm_obj_group zz
           where zz.vc_owner = t.vc_owner
           and t.vc_obj_name_zh like zz.vc_group_code
           and zz.vc_group_type='CUSTOM');

  COMMIT;
  --初始化视图
  insert into mdm_object
    (f_obj_id, vc_owner, vc_obj_name, vc_obj_type, vc_isused, d_updatetime)
    select seq_mdm_object.nextval,
           tt.vc_owner,
           d.VIEW_name,
           'VIEW',
           '1',
           SYSDATE
      from DBA_VIEWS d, mdm_owner tt
     where d.owner = tt.vc_owner
       and not exists (select 1
              from mdm_object zz
             where zz.vc_owner = tt.vc_owner
               and d.VIEW_name = zz.vc_obj_name);
  --更新使用状态
  update mdm_object t
     set t.vc_isused = '0'
   where t.vc_obj_type = 'VIEW'
     AND NOT EXISTS (SELECT 1
            FROM DBA_VIEWS ZZ
           WHERE ZZ.OWNER = T.VC_OWNER
             AND ZZ.VIEW_NAME = T.VC_OBJ_NAME);
  --初始化proc
  insert into mdm_object
    (f_obj_id, vc_owner, vc_obj_name, vc_obj_type, vc_isused, d_updatetime)
    select seq_mdm_object.nextval,
           tt.vc_owner,
           d.OBJECT_name ||
           nvl2(d.PROCEDURE_NAME, '.' || d.PROCEDURE_NAME, null),
           'PROCEDURE',
           '1',
           SYSDATE
      from dba_procedures d, mdm_owner tt
     where d.owner = tt.vc_owner
       and not exists
     (select 1
              from mdm_object zz
             where zz.vc_owner = tt.vc_owner
               and d.object_name ||
                   nvl2(d.PROCEDURE_NAME, '.' || d.PROCEDURE_NAME, null) =
                   zz.vc_obj_name);
  --更新使用状态
  update mdm_object t
     set t.vc_isused = '0'
   where t.vc_obj_type = 'PROCEDURE'
     AND NOT EXISTS
   (SELECT 1
            FROM dba_procedures ZZ
           WHERE ZZ.OWNER = T.VC_OWNER
             AND ZZ.OBJECT_NAME ||
                 nvl2(zz.PROCEDURE_NAME, '.' || zz.PROCEDURE_NAME, null) =
                 T.VC_OBJ_NAME);
  COMMIT;
  --初始别名
  insert into mdm_object
    (f_obj_id,
     vc_owner,
     vc_obj_name,
     vc_obj_type,
     VC_Dependencies_OWNER,
     VC_Dependencies_TABLE_NAME,
     vc_isused,
     d_updatetime)
    SELECT seq_mdm_object.nextval,
           t.owner,
           t.synonym_name,
           'SYNONYM',
           case
             when t.table_owner is null then
              (select username
                 from dba_db_links zz
                where zz.db_link = t.db_link
                  and zz.owner = t.owner)
             else
              t.table_owner
           end,
           t.table_name,
           '1',
           SYSDATE
      FROM DBA_SYNONYMS T, mdm_owner dd
     WHERE t.owner = dd.vc_owner
       AND NOT EXISTS (SELECT 1
              FROM MDM_OBJECT EE
             WHERE EE.VC_OWNER = T.owner
               AND EE.VC_OBJ_NAME = T.synonym_name);
  UPDATE mdm_object T
     SET t.vc_isused = '0'
   WHERE NOT EXISTS (SELECT 1
            FROM DBA_SYNONYMS EE
           WHERE t.VC_OWNER = ee.owner
             AND t.VC_OBJ_NAME = ee.synonym_name)
     AND t.vc_obj_type = 'SYNONYM';
  COMMIT;
  --更新comments
  update mdm_object t
     set t.vc_obj_name_zh =
         (select d.comments
            from dba_tab_comments d
           where d.owner = t.vc_owner
             and d.table_name = t.vc_obj_name)
   where t.vc_isused = '1';
  commit;
  --更新对象是否显示，以TEMP_开头的不显示
  update mdm_object t
     set t.vc_isshow = '0'
   where t.vc_obj_name like 'TEMP%';
  commit;

EXCEPTION
  WHEN OTHERS THEN
    O_ERRCODE := SQLCODE;
    O_ERRMSG  := SUBSTR('未处理异常:' || SQLERRM || '。' ||
                        DBMS_UTILITY.FORMAT_ERROR_BACKTRACE,
                        1,
                        1000);

END P_MDM_OBJECT;
```