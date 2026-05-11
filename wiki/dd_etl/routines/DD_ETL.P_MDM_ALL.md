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
  - "[[tables/mdm_obj_item|mdm_obj_item]]"
  - "[[tables/mdm_obj_tree|mdm_obj_tree]]"
  - "[[tables/mdm_object|mdm_object]]"
  - "[[tables/mdm_proc_proc|mdm_proc_proc]]"
  - "[[tables/mdm_proc_table|mdm_proc_table]]"
  - "[[tables/mdm_proc_table_physics|mdm_proc_table_physics]]"
  - "[[tables/mdm_table_proc|mdm_table_proc]]"
routine_type: PROCEDURE
---

# ⚙️ DD_ETL.P_MDM_ALL

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `PROCEDURE`
:::

---

## 🔗 相关表
- [mdm_obj_ddl](../tables/mdm_obj_ddl.md)
- [mdm_obj_item](../tables/mdm_obj_item.md)
- [mdm_obj_tree](../tables/mdm_obj_tree.md)
- [mdm_object](../tables/mdm_object.md)
- [mdm_proc_proc](../tables/mdm_proc_proc.md)
- [mdm_proc_table](../tables/mdm_proc_table.md)
- [mdm_proc_table_physics](../tables/mdm_proc_table_physics.md)
- [mdm_table_proc](../tables/mdm_table_proc.md)

---

## 📜 源码
```sql
PROCEDURE        P_MDM_ALL(I_STARTDATE in varchar2,
                                            I_ENDDATE   in varchar2,
                                            O_ERRCODE   OUT INTEGER,
                                            O_ERRMSG    OUT VARCHAR2) IS
--  V_NUMBER NUMBER(10); --记录条数
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''YYYY-MM-DD''';
  O_ERRCODE := 0;
  O_ERRMSG  := '运行成功';
  --清空历史记录
  EXECUTE IMMEDIATE 'TRUNCATE TABLE mdm_object';
  EXECUTE IMMEDIATE 'TRUNCATE TABLE mdm_obj_tree';
  EXECUTE IMMEDIATE 'TRUNCATE TABLE mdm_obj_ddl';
  EXECUTE IMMEDIATE 'TRUNCATE TABLE mdm_obj_item';
  EXECUTE IMMEDIATE 'TRUNCATE TABLE mdm_proc_proc';
  EXECUTE IMMEDIATE 'TRUNCATE TABLE mdm_proc_table';
  EXECUTE IMMEDIATE 'TRUNCATE TABLE mdm_table_proc';
  EXECUTE IMMEDIATE 'TRUNCATE TABLE mdm_proc_table_physics';

  --初始化对象（表、视图、存储过程、同义词）+备注
  P_MDM_OBJECT(I_STARTDATE,I_ENDDATE,O_ERRCODE,O_ERRMSG);
  --生成页面查询的树形结构（根据对象类型分组+业务类型分组）
  P_MDM_OBJ_TREE(I_STARTDATE,I_ENDDATE,O_ERRCODE,O_ERRMSG);
  --保存表、视图的字段+备注
  P_MDM_OBJ_ITEM(I_STARTDATE,I_ENDDATE,O_ERRCODE,O_ERRMSG);
  --保存对象的DDL语句
  P_MDM_OBJ_DDL(I_STARTDATE,I_ENDDATE,O_ERRCODE,O_ERRMSG);
  --保存过程引用对象的关联关系
  P_MDM_PROC_TABLE(I_STARTDATE,I_ENDDATE,O_ERRCODE,O_ERRMSG);
  --保存表的数据来源过程（解析过程代码确定 更新语句的行，从而确定xxx表的来源过程）
  P_MDM_TABLE_PROC(I_STARTDATE,I_ENDDATE,O_ERRCODE,O_ERRMSG);
  --保存过程引用其他过程的关联关系，同时保存，过程引用对象的关系（不在MDM_PROC_TABLE中）
  P_MDM_PROC_PROC(I_STARTDATE,I_ENDDATE,O_ERRCODE,O_ERRMSG);
  --保存过程引用的同义词对应的具体物理表
  p_mdm_proc_table_physics(I_STARTDATE,I_ENDDATE,O_ERRCODE,O_ERRMSG);

  COMMIT;

EXCEPTION
  WHEN OTHERS THEN
    O_ERRCODE := SQLCODE;
    O_ERRMSG  := SUBSTR('未处理异常:' || SQLERRM || '。' ||
                        DBMS_UTILITY.FORMAT_ERROR_BACKTRACE,
                        1,
                        1000);

END P_MDM_ALL;
```