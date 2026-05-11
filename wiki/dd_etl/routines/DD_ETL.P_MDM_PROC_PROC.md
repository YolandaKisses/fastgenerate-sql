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
  - "[[tables/mdm_owner|mdm_owner]]"
  - "[[tables/mdm_proc_proc|mdm_proc_proc]]"
  - "[[tables/mdm_proc_table|mdm_proc_table]]"
  - "[[tables/temp_mdm_dba_dependencies|temp_mdm_dba_dependencies]]"
  - "[[tables/temp_mdm_dba_procedures|temp_mdm_dba_procedures]]"
  - "[[tables/temp_mdm_dba_source|temp_mdm_dba_source]]"
  - "[[tables/temp_mdm_proc_relation_tab|temp_mdm_proc_relation_tab]]"
  - "[[tables/temp_mdm_source_procedurce|temp_mdm_source_procedurce]]"
routine_type: PROCEDURE
---

# ⚙️ DD_ETL.P_MDM_PROC_PROC

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `PROCEDURE`
:::

---

## 🔗 相关表
- [mdm_object](../tables/mdm_object.md)
- [mdm_owner](../tables/mdm_owner.md)
- [mdm_proc_proc](../tables/mdm_proc_proc.md)
- [mdm_proc_table](../tables/mdm_proc_table.md)
- [temp_mdm_dba_dependencies](../tables/temp_mdm_dba_dependencies.md)
- [temp_mdm_dba_procedures](../tables/temp_mdm_dba_procedures.md)
- [temp_mdm_dba_source](../tables/temp_mdm_dba_source.md)
- [temp_mdm_proc_relation_tab](../tables/temp_mdm_proc_relation_tab.md)
- [temp_mdm_source_procedurce](../tables/temp_mdm_source_procedurce.md)

---

## 📜 源码
```sql
PROCEDURE        P_MDM_PROC_PROC(I_STARTDATE in varchar2,
                                            I_ENDDATE   in varchar2,
                                            O_ERRCODE   OUT INTEGER,
                                            O_ERRMSG    OUT VARCHAR2) AUTHID  CURRENT_USER IS
  V_NUMBER NUMBER(10); --记录条数,目前表的来自哪些存储过程只针对本用户下进行搜索，剔除函数
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''YYYY-MM-DD''';
  O_ERRCODE := 0;
  O_ERRMSG  := '运行成功';
  execute immediate 'truncate table TEMP_MDM_SOURCE_PROCEDURCE';
  execute immediate 'truncate table TEMP_MDM_PROC_RELATION_TAB';
  execute immediate 'truncate table temp_mdm_dba_source';
  execute immediate 'truncate table TEMP_MDM_DBA_PROCEDURES';
  execute immediate 'truncate table TEMP_MDM_DBA_DEPENDENCIES';


  --找到用户下包中的函数或者存储过程的开始行和结束行
 insert into temp_mdm_dba_source
   (OWNER, NAME, TYPE, LINE, TEXT)
   select T.OWNER, t.name, t.type, t.line, t.text
     from dba_source t
    where t.TYPE = 'PACKAGE BODY'
      and exists
    (select 1 from mdm_owner zz where zz.vc_owner = t.owner);
 commit;
 insert into TEMP_MDM_DBA_PROCEDURES
   (owner,
    object_name,
    procedure_name,
    object_id,
    subprogram_id,
    overload,
    object_type,
    aggregate,
    pipelined,
    impltypeowner,
    impltypename,
    parallel,
    interface,
    deterministic,
    authid)
   select owner,
          object_name,
          procedure_name,
          object_id,
          subprogram_id,
          overload,
          object_type,
          aggregate,
          pipelined,
          impltypeowner,
          impltypename,
          parallel,
          interface,
          deterministic,
          authid
     from sys.dba_procedures t
    where t.procedure_name is not null
      and exists
    (select 1 from mdm_owner zz where zz.vc_owner = t.owner);
 commit;
 insert into TEMP_MDM_DBA_DEPENDENCIES
   (owner,
    name,
    type,
    referenced_owner,
    referenced_name,
    referenced_type,
    referenced_link_name,
    dependency_type)
   select owner,
          name,
          type,
          referenced_owner,
          referenced_name,
          referenced_type,
          referenced_link_name,
          dependency_type
     from dba_dependencies t
    where exists (select 1 from mdm_owner zz where zz.vc_owner = t.owner);
 commit;

  insert into TEMP_MDM_SOURCE_PROCEDURCE
    (OBJECT_NAME, PROCEDURE_NAME, OWNER, NAME, TYPE, LINE, TEXT)
    select dd.object_name, dd.procedure_name, t.OWNER, t.NAME, t.TYPE, t.LINE, t.TEXT
      from temp_mdm_dba_source t,
           TEMP_MDM_DBA_PROCEDURES DD
     where T.TYPE = 'PACKAGE BODY'
       AND T.OWNER = DD.OWNER
       AND t.name = dd.object_name
       and (nvl(regexp_substr(upper(t.text),
                              '[[:space:]]*?PROCEDURE[[:space:]]+?' ||
                              dd.procedure_name || '([[:space:]]+?|\()+?'),
                '0') <> '0'

          /* or (nvl(regexp_substr(upper(t.text),
                              '[[:space:]]*?FUNCTION[[:space:]]+?' ||
                              dd.procedure_name || '([[:space:]]+?|\()+?'),
                '0') <> '0')
           or  (nvl(regexp_substr(UPPER(t.text),
                              '[[:space:]]*?END[[:space:]]+?' ||
                              dd.procedure_name || ';'),
                '0') <> '0')         */
           );
  commit;

  insert into TEMP_MDM_SOURCE_PROCEDURCE
    (OBJECT_NAME, PROCEDURE_NAME, OWNER, NAME, TYPE, LINE, TEXT)
    select dd.object_name, dd.procedure_name, t.OWNER, t.NAME, t.TYPE, t.LINE, t.TEXT
      from temp_mdm_dba_source t,
           TEMP_MDM_DBA_PROCEDURES DD
     where T.TYPE = 'PACKAGE BODY'
       AND T.OWNER = DD.OWNER
       AND t.name = dd.object_name
       and nvl(regexp_substr(upper(t.text),
                              '[[:space:]]*?FUNCTION[[:space:]]+?' ||
                              dd.procedure_name || '([[:space:]]+?|\()+?'),
                '0') <> '0';
  commit;

  insert into TEMP_MDM_SOURCE_PROCEDURCE
    (OBJECT_NAME, PROCEDURE_NAME, OWNER, NAME, TYPE, LINE, TEXT)
    select dd.object_name, dd.procedure_name, t.OWNER, t.NAME, t.TYPE, t.LINE, t.TEXT
      from temp_mdm_dba_source t,
           TEMP_MDM_DBA_PROCEDURES DD
     where T.TYPE = 'PACKAGE BODY'
       AND T.OWNER = DD.OWNER
       AND t.name = dd.object_name
       and (nvl(regexp_substr(UPPER(t.text),
                              '[[:space:]]*?END[[:space:]]+?' ||
                              dd.procedure_name || ';'),
                '0') <> '0');
  commit;
  --更新包体中的函数或者存储过程的结束行
  update TEMP_MDM_SOURCE_PROCEDURCE t
     set t.maxline = (select max(line)
                        from TEMP_MDM_SOURCE_PROCEDURCE d
                       where t.object_name = d.object_name
                         and t.procedure_name = d.procedure_name
                         and t.owner = d.owner);
  --删除包体中的函数、存储过程的最大行数的记录
  delete from TEMP_MDM_SOURCE_PROCEDURCE t
   where t.line =
         (select max(line)
            from TEMP_MDM_SOURCE_PROCEDURCE dd
           where dd.object_name = t.object_name
             and t.procedure_name = dd.procedure_name
             and t.owner = dd.owner
           group by dd.object_name, dd.procedure_name, dd.owner
          having count(dd.object_name || dd.procedure_name || dd.owner) >= 2);
  commit;
  --保存 包、函数、存储过程中更新或者插入的行数保存到临时表中
  insert into TEMP_MDM_PROC_RELATION_TAB
    (OWNER,
     NAME,
     TYPE,
     VC_OBJ_NAME,
     line,
     vc_owner,
     vc_obj_type

     )
    SELECT d.owner,
           d.name,
           d.type,
           dd.referenced_name,
           d.line,
           DD.referenced_owner,
           dd.referenced_type
      FROM temp_mdm_dba_source D, TEMP_MDM_DBA_DEPENDENCIES DD
     WHERE D.OWNER = DD.owner
       AND D.name = DD.name
       AND DD.referenced_type ='FUNCTION'
       and d.type = 'PACKAGE BODY'
       AND (nvl(regexp_substr(upper(D.text),
                              '([[:space:]]*?||\.{1})' || DD.referenced_name ||
                              '([[:space:]]+?|\({1})'),
                '0') <> '0');
  COMMIT;

   insert into TEMP_MDM_PROC_RELATION_TAB
    (OWNER,
     NAME,
     TYPE,
     VC_OBJ_NAME,
     line,
     vc_owner,
     vc_obj_type

     )
    SELECT d.owner,
           d.name,
           d.type,
           dd.referenced_name,
           d.line,
           DD.referenced_owner,
           dd.referenced_type
      FROM temp_mdm_dba_source D, TEMP_MDM_DBA_DEPENDENCIES DD
     WHERE D.OWNER = DD.owner
       AND D.name = DD.name
       AND DD.referenced_type = 'PROCEDURE'
       and d.type = 'PACKAGE BODY'
       AND (nvl(regexp_substr(upper(D.text),
                              '([[:space:]]*?||\.{1})' || DD.referenced_name ||
                              '([[:space:]]+?|\({1})'),
                '0') <> '0');


 insert into TEMP_MDM_PROC_RELATION_TAB
    (OWNER,
     NAME,
     TYPE,
     VC_OBJ_NAME,
     line,
     vc_owner,
     vc_obj_type

     )
    SELECT d.owner,
           d.name,
           d.type,
           dd.referenced_name,
           d.line,
           DD.referenced_owner,
           dd.referenced_type
      FROM temp_mdm_dba_source D, TEMP_MDM_DBA_DEPENDENCIES DD
     WHERE D.OWNER = DD.owner
       AND D.name = DD.name
       AND DD.referenced_type = 'TABLE'
       and d.type = 'PACKAGE BODY'
       AND (nvl(regexp_substr(upper(D.text),
                              '([[:space:]]*?||\.{1})' || DD.referenced_name ||
                              '([[:space:]]+?|\({1})'),
                '0') <> '0');
   insert into TEMP_MDM_PROC_RELATION_TAB
    (OWNER,
     NAME,
     TYPE,
     VC_OBJ_NAME,
     line,
     vc_owner,
     vc_obj_type

     )
    SELECT d.owner,
           d.name,
           d.type,
           dd.referenced_name,
           d.line,
           DD.referenced_owner,
           dd.referenced_type
      FROM temp_mdm_dba_source D, TEMP_MDM_DBA_DEPENDENCIES DD
     WHERE D.OWNER = DD.owner
       AND D.name = DD.name
       AND DD.referenced_type = 'SYNONYM'
       and d.type = 'PACKAGE BODY'
       AND (nvl(regexp_substr(upper(D.text),
                              '([[:space:]]*?||\.{1})' || DD.referenced_name ||
                              '([[:space:]]+?|\({1})'),
                '0') <> '0');
  COMMIT;

    --2015-12-23 14:27:53
    --添加 对 （ from 表名; ） 和（ 表名1,表名2） 的支持
   insert into TEMP_MDM_PROC_RELATION_TAB
    (OWNER,
     NAME,
     TYPE,
     VC_OBJ_NAME,
     line,
     vc_owner,
     vc_obj_type

     )
    SELECT d.owner,
           d.name,
           d.type,
           dd.referenced_name,
           d.line,
           DD.referenced_owner,
           dd.referenced_type
      FROM temp_mdm_dba_source D, TEMP_MDM_DBA_DEPENDENCIES DD, mdm_owner t
     WHERE D.OWNER = DD.owner
       and t.vc_owner = d.owner
       AND D.name = DD.name
       AND DD.referenced_type =
            'TABLE'
       and d.type = 'PACKAGE BODY'
       AND (
           nvl(regexp_substr(upper(D.text),
                              '([[:space:]]*?||\.{1})' || DD.referenced_name ||
                              '([[:space:]]*?\;{1})'),
                '0') <> '0'
                or
                nvl(regexp_substr(upper(D.text),
                              '([[:space:]]*?||\.{1})' || DD.referenced_name ||
                              '([[:space:]]*?\,{1})'),
                '0') <> '0'
                );
  COMMIT;
   insert into TEMP_MDM_PROC_RELATION_TAB
    (OWNER,
     NAME,
     TYPE,
     VC_OBJ_NAME,
     line,
     vc_owner,
     vc_obj_type

     )
    SELECT d.owner,
           d.name,
           d.type,
           dd.referenced_name,
           d.line,
           DD.referenced_owner,
           dd.referenced_type
      FROM temp_mdm_dba_source D, TEMP_MDM_DBA_DEPENDENCIES DD, mdm_owner t
     WHERE D.OWNER = DD.owner
       and t.vc_owner = d.owner
       AND D.name = DD.name
       AND DD.referenced_type =
            'SYNONYM'
       and d.type = 'PACKAGE BODY'
       AND (
           nvl(regexp_substr(upper(D.text),
                              '([[:space:]]*?||\.{1})' || DD.referenced_name ||
                              '([[:space:]]*?\;{1})'),
                '0') <> '0'
                or
                nvl(regexp_substr(upper(D.text),
                              '([[:space:]]*?||\.{1})' || DD.referenced_name ||
                              '([[:space:]]*?\,{1})'),
                '0') <> '0'
                );
  COMMIT;












  --获取包体中表的引用行(如何区分是函数与函数，还包体跟包体)
  /*insert into TEMP_MDM_PROC_RELATION_TAB
  (
         OWNER,
         NAME,
         TYPE,
         VC_OBJ_NAME,
         line,
         vc_owner,
         vc_obj_type

  )
  SELECT d.owner,d.name,d.type,dd.referenced_name,d.line,dd.referenced_name,dd.referenced_type FROM DBA_SOURCE D ,DBA_DEPENDENCIES DD,mdm_owner t
  WHERE D.OWNER=DD.owner
  and t.vc_owner=d.owner
  AND D.name=DD.name
  AND DD.referenced_type IN ('TABLE','SYNONYM')
  and d.type='PACKAGE BODY'
  AND (nvl(regexp_substr(upper(D.text),'[[:space:]]*?'||DD.referenced_name||'([[:space:]]+?|\({1})'),'0')<>'0'
  );*/
  COMMIT;
  --变更procedure_name='PACKAGE BODY'成该包体下的存储过程或者函数（需要修改）
  UPDATE TEMP_MDM_PROC_RELATION_TAB T
     SET T.procedure_name = (SELECT DD.PROCEDURE_NAME
                               FROM TEMP_MDM_SOURCE_PROCEDURCE dd
                              where t.owner = dd.owner
                                and t.name = dd.object_name
                                AND T.LINE BETWEEN DD.LINE AND DD.MAXLINE)
   WHERE T.TYPE = 'PACKAGE BODY';
  --清除重复记录
  DELETE FROM TEMP_MDM_PROC_RELATION_TAB T
   WHERE ROWID not in (SELECT max(ROWID)
                         FROM TEMP_MDM_PROC_RELATION_TAB XX
                        GROUP BY XX.OWNER,
                                 XX.NAME,
                                 XX.VC_OBJ_NAME,
                                 xx.procedure_name,
                                 xx.vc_owner
                       having count(*) >= 2)
     and rowid not in (SELECT max(ROWID)
                         FROM TEMP_MDM_PROC_RELATION_TAB XX
                        GROUP BY XX.OWNER,
                                 XX.NAME,
                                 XX.VC_OBJ_NAME,
                                 xx.procedure_name,
                                 xx.vc_owner
                       having count(*) = 1);
  commit;
  --变更vc_obj_name 为对象对应的id号
  update TEMP_MDM_PROC_RELATION_TAB t
     set t.vc_obj_name = (select d.f_obj_id
                            from mdm_object d
                           where t.vc_owner = d.vc_owner
                             and t.vc_obj_name = d.vc_obj_name);
  --变更存储过程、函数为该对象的id号
  update TEMP_MDM_PROC_RELATION_TAB t
     set t.name = (select d.f_obj_id
                     from mdm_object d
                    where t.owner = d.vc_owner
                      and t.name || '.' || t.procedure_name = d.vc_obj_name)
   where t.type = 'PACKAGE BODY';
  update TEMP_MDM_PROC_RELATION_TAB t
     set t.name = (select d.f_obj_id
                     from mdm_object d
                    where t.owner = d.vc_owner
                      and t.name = d.vc_obj_name)
   where t.type <> 'PACKAGE BODY';
  --剔除不存在的对象
  delete from TEMP_MDM_PROC_RELATION_TAB t
   where t.name is null
      or t.vc_obj_name is null;
  --delete from TEMP_MDM_PROC_RELATION_TAB t where t.name=t.vc_obj_name;
  commit;
  --保存表和函数或者存储过程关系
  insert into mdm_proc_proc
    (f_p_proc_id, f_proc_id, vc_isauto, d_updatetime)
    select t.name, t.vc_obj_name, '1', sysdate
      from TEMP_MDM_PROC_RELATION_TAB t
     WHERE NOT EXISTS (SELECT 1
              FROM mdm_proc_proc DD
             WHERE T.NAME = DD.F_P_PROC_ID
               AND T.VC_OBJ_NAME = DD.F_PROC_ID)
       and T.vc_obj_type in ('FUNCTION', 'PROCEDURE');
  commit;
  UPDATE mdm_proc_proc T
     SET T.VC_ISAUTO = '0'
   WHERE NOT EXISTS
   (SELECT 1
            FROM TEMP_MDM_PROC_RELATION_TAB ZZ
           WHERE ZZ.NAME = T.F_P_PROC_ID
             AND ZZ.VC_OBJ_NAME = t.f_proc_id
             and ZZ.vc_obj_type in ('FUNCTION', 'PROCEDURE'));
  commit;
  --保存存储过程和表的关系
    insert into mdm_proc_table
    (f_proc_id, f_table_id, vc_isauto, d_updatetime)
    select T.NAME, T.VC_OBJ_NAME, '1', SYSDATE
      from TEMP_MDM_PROC_RELATION_TAB t
     where not exists (select 1
              from mdm_proc_table dd
             where dd.f_table_id = t.vc_obj_name
               and dd.f_proc_id = t.name)
       and t.vc_obj_type in ('TABLE', 'SYNONYM');
  COMMIT;
  UPDATE MDM_PROC_TABLE T
     SET T.VC_ISAUTO = '0'
   WHERE NOT EXISTS (SELECT 1
            FROM TEMP_MDM_PROC_RELATION_TAB DD
           WHERE DD.NAME = T.F_PROC_ID
             AND DD.VC_OBJ_NAME = T.F_TABLE_ID
             AND DD.VC_OBJ_TYPE IN ('TABLE', 'SYNONYM'))
     AND NOT EXISTS
   (SELECT 1
            FROM (select (SELECT D.F_OBJ_ID
                            FROM MDM_OBJECT D
                           WHERE D.VC_OBJ_NAME = T.name
                             AND T.owner = D.VC_OWNER) F_PROC_ID,
                         (SELECT D.F_OBJ_ID
                            FROM MDM_OBJECT D
                           WHERE D.VC_OBJ_NAME = T.referenced_name
                             AND T.referenced_owner = D.VC_OWNER) AS F_TABLE_ID,
                         '1',
                         SYSDATE
                    from TEMP_MDM_DBA_DEPENDENCIES t, MDM_OBJECT ZZ
                   where t.name = ZZ.VC_OBJ_NAME
                     AND ZZ.VC_OBJ_TYPE = 'PROCEDURES'
                     AND T.owner = ZZ.VC_OWNER
                     AND EXISTS
                   (SELECT 1
                            FROM MDM_OBJECT DD
                           WHERE DD.VC_OBJ_NAME = T.referenced_name
                             AND DD.VC_OWNER = T.referenced_owner)) A
           WHERE A.F_PROC_ID = T.F_PROC_ID
             AND A.F_TABLE_ID = T.F_TABLE_ID);
  COMMIT;

EXCEPTION
  WHEN OTHERS THEN
    O_ERRCODE := SQLCODE;
    O_ERRMSG  := SUBSTR('未处理异常:' || SQLERRM || '。' ||
                        DBMS_UTILITY.FORMAT_ERROR_BACKTRACE,
                        1,
                        1000);

END P_MDM_PROC_PROC;
```