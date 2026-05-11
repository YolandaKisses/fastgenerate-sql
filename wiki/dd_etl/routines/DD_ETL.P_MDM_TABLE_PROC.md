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
  - "[[tables/mdm_table_proc|mdm_table_proc]]"
  - "[[tables/temp_mdm_dba_procedures|temp_mdm_dba_procedures]]"
  - "[[tables/temp_mdm_dba_source|temp_mdm_dba_source]]"
  - "[[tables/temp_mdm_proc_relation_tab|temp_mdm_proc_relation_tab]]"
  - "[[tables/temp_mdm_source_procedurce|temp_mdm_source_procedurce]]"
routine_type: PROCEDURE
---

# ⚙️ DD_ETL.P_MDM_TABLE_PROC

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `PROCEDURE`
:::

---

## 🔗 相关表
- [mdm_object](../tables/mdm_object.md)
- [mdm_owner](../tables/mdm_owner.md)
- [mdm_table_proc](../tables/mdm_table_proc.md)
- [temp_mdm_dba_procedures](../tables/temp_mdm_dba_procedures.md)
- [temp_mdm_dba_source](../tables/temp_mdm_dba_source.md)
- [temp_mdm_proc_relation_tab](../tables/temp_mdm_proc_relation_tab.md)
- [temp_mdm_source_procedurce](../tables/temp_mdm_source_procedurce.md)

---

## 📜 源码
```sql
PROCEDURE        P_MDM_TABLE_PROC(I_STARTDATE in varchar2,
                                             I_ENDDATE   in varchar2,
                                             O_ERRCODE   OUT INTEGER,
                                             O_ERRMSG    OUT VARCHAR2) IS
  V_NUMBER NUMBER(10); --记录条数,目前表的来自哪些存储过程只针对本用户下进行搜索，剔除函数
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''YYYY-MM-DD''';
  O_ERRCODE := 0;
  O_ERRMSG  := '运行成功';
  --清空临时表
  execute immediate 'truncate table TEMP_MDM_SOURCE_PROCEDURCE';
  execute immediate 'truncate table TEMP_MDM_PROC_RELATION_TAB';
  execute immediate 'truncate table temp_mdm_dba_source';
  execute immediate 'truncate table TEMP_MDM_DBA_PROCEDURES';
  --找到用户下包中的函数或者存储过程的开始行和结束行
  insert into temp_mdm_dba_source (OWNER, NAME, TYPE, LINE, TEXT)
  select  T.OWNER,t.name,t.type,t.line,t.text from dba_source t
      where t.TYPE='PACKAGE BODY'
   and exists(select 1 from mdm_owner zz where zz.vc_owner=t.owner);
  commit;
  insert into TEMP_MDM_DBA_PROCEDURES
    (owner, object_name, procedure_name, object_id, subprogram_id, overload, object_type, aggregate, pipelined, impltypeowner, impltypename, parallel, interface, deterministic, authid)
  select owner, object_name, procedure_name, object_id, subprogram_id, overload, object_type, aggregate, pipelined, impltypeowner, impltypename, parallel, interface, deterministic, authid

   from sys.dba_procedures t where t.procedure_name is not null
    and exists(select 1 from mdm_owner zz where zz.vc_owner = t.owner);
  commit;

  insert into TEMP_MDM_SOURCE_PROCEDURCE
    (OBJECT_NAME, PROCEDURE_NAME, OWNER, NAME, TYPE, LINE, TEXT)
    select dd.object_name, dd.procedure_name, T.OWNER,t.name,t.type,t.line,t.text
      from temp_mdm_dba_source t,
           TEMP_MDM_DBA_PROCEDURES DD
     where T.TYPE = 'PACKAGE BODY'
       AND T.OWNER = DD.OWNER
       AND t.name = dd.object_name
       and (nvl(regexp_substr(upper(t.text),
                              '[[:space:]]*?PROCEDURE[[:space:]]+?' ||
                              dd.procedure_name || '([[:space:]]+?|\()+?'),
                '0') <> '0');

  insert into TEMP_MDM_SOURCE_PROCEDURCE
    (OBJECT_NAME, PROCEDURE_NAME, OWNER, NAME, TYPE, LINE, TEXT)
    select dd.object_name, dd.procedure_name, T.*
      from temp_mdm_dba_source t,
           TEMP_MDM_DBA_PROCEDURES DD
     where T.TYPE = 'PACKAGE BODY'
       AND T.OWNER = DD.OWNER
       AND t.name = dd.object_name
       and (nvl(regexp_substr(upper(t.text),
                              '[[:space:]]*?FUNCTION[[:space:]]+?' ||
                              dd.procedure_name || '([[:space:]]+?|\()+?'),
                '0') <> '0');

  insert into TEMP_MDM_SOURCE_PROCEDURCE
    (OBJECT_NAME, PROCEDURE_NAME, OWNER, NAME, TYPE, LINE, TEXT)
    select dd.object_name, dd.procedure_name, T.*
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



 --保存 包、函数、存储过程中 INSERT 行数保存到临时表中
  FOR CC IN (select t.owner, T.name, T.TYPE, dd.Vc_Obj_Name, t.line
               from (select *
                       from MDM_OBJECT t
                      where exists (select 1
                               from dba_dependencies dd
                              where dd.referenced_owner = t.VC_owner
                                and dd.referenced_name = T.VC_OBJ_NAME)
                        and t.vc_obj_type = 'TABLE') DD,
                    (SELECT *
                       FROM temp_mdm_dba_source T, mdm_owner dd
                      WHERE nvl(regexp_substr(upper(t.text),
    '(([[:space:]]*?INSERT[[:space:]]+?INTO[[:space:]]+?))'),
                                '0') <> '0'
                        and t.owner = dd.vc_owner
                        and t.type in
                            ('PROCEDURE', 'PACKAGE BODY', 'FUNCTION')) t
              where T.OWNER = DD.VC_OWNER
                AND (
                nvl(regexp_substr(upper(t.text),
                                       '[[:space:]]*?INSERT[[:space:]]+?INTO[[:space:]]+?' ||
                                       DD.VC_OBJ_NAME || '[[:space:]]+?'),
                         '0') <> '0' )) LOOP
    INSERT INTO TEMP_MDM_PROC_RELATION_TAB
      (OWNER,
       NAME,
       TYPE,
       VC_OBJ_NAME,
       line

       )
    VALUES
      (CC.OWNER, CC.NAME, CC.TYPE, CC.VC_OBJ_NAME, cc.line);
    commit;
  END LOOP;
  COMMIT;

  --保存 包、函数、存储过程中merge into行数保存到临时表中
  FOR CC IN (select t.owner, T.name, T.TYPE, dd.Vc_Obj_Name, t.line
               from (select *
                       from MDM_OBJECT t
                      where exists (select 1
                               from dba_dependencies dd
                              where dd.referenced_owner = t.VC_owner
                                and dd.referenced_name = T.VC_OBJ_NAME)
                        and t.vc_obj_type = 'TABLE') DD,
                    (SELECT *
                       FROM temp_mdm_dba_source T, mdm_owner dd
                      WHERE nvl(regexp_substr(upper(t.text),
    '(([[:space:]]*?MERGE[[:space:]]+?INTO[[:space:]]+?))'),
                                '0') <> '0'
                        and t.owner = dd.vc_owner
                        and t.type in
                            ('PROCEDURE', 'PACKAGE BODY', 'FUNCTION')) t
              where T.OWNER = DD.VC_OWNER
                AND (
                nvl(regexp_substr(upper(t.text),
                                       '[[:space:]]*?MERGE[[:space:]]+?INTO[[:space:]]+?' ||
                                       DD.VC_OBJ_NAME || '[[:space:]]+?'),
                         '0') <> '0' )) LOOP
    INSERT INTO TEMP_MDM_PROC_RELATION_TAB
      (OWNER,
       NAME,
       TYPE,
       VC_OBJ_NAME,
       line

       )
    VALUES
      (CC.OWNER, CC.NAME, CC.TYPE, CC.VC_OBJ_NAME, cc.line);
    commit;
  END LOOP;
  COMMIT;


  --保存 包、函数、存储过程中update行数保存到临时表中
  FOR CC IN (select t.owner, T.name, T.TYPE, dd.Vc_Obj_Name, t.line
               from (select *
                       from MDM_OBJECT t
                      where exists (select 1
                               from dba_dependencies dd
                              where dd.referenced_owner = t.VC_owner
                                and dd.referenced_name = T.VC_OBJ_NAME)
                        and t.vc_obj_type = 'TABLE') DD,
                    (SELECT *
                       FROM temp_mdm_dba_source T, mdm_owner dd
                      WHERE nvl(regexp_substr(upper(t.text),
    '(([[:space:]]*?UPDATE[[:space:]]+?))'),
                                '0') <> '0'
                        and t.owner = dd.vc_owner
                        and t.type in
                            ('PROCEDURE', 'PACKAGE BODY', 'FUNCTION')) t
              where T.OWNER = DD.VC_OWNER
                AND (
                    nvl(regexp_substr(UPPER(t.text),
                                       '[[:space:]]*?UPDATE[[:space:]]+?' ||
                                       DD.VC_OBJ_NAME || '[[:space:]]+?'),
                         '0') <> '0')) LOOP
    INSERT INTO TEMP_MDM_PROC_RELATION_TAB
      (OWNER,
       NAME,
       TYPE,
       VC_OBJ_NAME,
       line

       )
    VALUES
      (CC.OWNER, CC.NAME, CC.TYPE, CC.VC_OBJ_NAME, cc.line);
    commit;
  END LOOP;
  COMMIT;



  --变更procedure_name='PACKAGE BODY'成该包体下的存储过程或者函数
  UPDATE TEMP_MDM_PROC_RELATION_TAB T
     SET T.procedure_name = (SELECT DD.PROCEDURE_NAME
                               FROM TEMP_MDM_SOURCE_PROCEDURCE dd
                              where t.owner = dd.owner
                                and t.name = dd.object_name
                                AND T.LINE BETWEEN DD.LINE AND DD.MAXLINE
                                and rownum=1)
   WHERE T.TYPE = 'PACKAGE BODY';
  commit;
  --清除该包体中不存在的函数、存储过程
  delete from TEMP_MDM_PROC_RELATION_TAB t
   where t.type = 'PACKAGE BODY'
     and t.procedure_name is null;
  commit;
  --清除重复记录
  DELETE FROM TEMP_MDM_PROC_RELATION_TAB T
   WHERE ROWID not in
         (SELECT max(ROWID)
            FROM TEMP_MDM_PROC_RELATION_TAB XX
           GROUP BY XX.OWNER, XX.NAME, XX.VC_OBJ_NAME, xx.procedure_name
          having count(*) >= 2)
     and rowid not in
         (SELECT max(ROWID)
            FROM TEMP_MDM_PROC_RELATION_TAB XX
           GROUP BY XX.OWNER, XX.NAME, XX.VC_OBJ_NAME, xx.procedure_name
          having count(*) = 1);
  commit;
  --变更vc_obj_name 为对象对应的id号
  update TEMP_MDM_PROC_RELATION_TAB t
     set t.vc_obj_name = (select d.f_obj_id
                            from mdm_object d
                           where t.owner = d.vc_owner
                             and t.vc_obj_name = d.vc_obj_name);
  --变更存储过程、函数为该对象的id号
  update TEMP_MDM_PROC_RELATION_TAB t
     set t.name = (select d.f_obj_id
                     from mdm_object d
                    where t.owner = d.vc_owner
                      and t.name || '.' || t.procedure_name = d.vc_obj_name
                      and rownum=1)
   where t.type = 'PACKAGE BODY';
  update TEMP_MDM_PROC_RELATION_TAB t
     set t.name = (select d.f_obj_id
                     from mdm_object d
                    where t.owner = d.vc_owner
                      and t.name = d.vc_obj_name
                      and rownum=1)
   where t.type <> 'PACKAGE BODY';
  --剔除不存在的对象
  delete from TEMP_MDM_PROC_RELATION_TAB t
   where t.name is null
      or t.vc_obj_name is null;
  --保存表和函数或者存储过程关系
  insert into mdm_table_proc
    (f_table_id, f_proc_id, f_level, vc_isauto, d_updatetime)
    select t.vc_obj_name, t.name, '1', '1', sysdate
      from TEMP_MDM_PROC_RELATION_TAB t
     where not exists (select 1
              from mdm_table_proc zz
             where zz.f_table_id = t.vc_obj_name
               and zz.f_proc_id = t.name);
  commit;
  update mdm_table_proc t
     set t.vc_isauto = '0'
   where not exists (select 1
            from TEMP_MDM_PROC_RELATION_TAB zz
           where zz.name = t.f_proc_id
             and zz.vc_obj_name = t.f_table_id);
  commit;
EXCEPTION
  WHEN OTHERS THEN
    O_ERRCODE := SQLCODE;
    O_ERRMSG  := SUBSTR('未处理异常:' || SQLERRM || '。' ||
                        DBMS_UTILITY.FORMAT_ERROR_BACKTRACE,
                        1,
                        1000);

END P_MDM_TABLE_PROC;
```