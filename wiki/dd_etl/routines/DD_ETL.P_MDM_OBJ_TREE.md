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
  - "[[tables/mdm_obj_tree|mdm_obj_tree]]"
  - "[[tables/mdm_object|mdm_object]]"
  - "[[tables/mdm_owner|mdm_owner]]"
routine_type: PROCEDURE
---

# ⚙️ DD_ETL.P_MDM_OBJ_TREE

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `PROCEDURE`
:::

---

## 🔗 相关表
- [mdm_obj_group](../tables/mdm_obj_group.md)
- [mdm_obj_tree](../tables/mdm_obj_tree.md)
- [mdm_object](../tables/mdm_object.md)
- [mdm_owner](../tables/mdm_owner.md)

---

## 📜 源码
```sql
PROCEDURE        P_MDM_OBJ_TREE(I_STARTDATE in varchar2,
                                         I_ENDDATE   in varchar2,
                                         O_ERRCODE   OUT INTEGER,
                                         O_ERRMSG    OUT VARCHAR2) IS
  V_NUMBER NUMBER(10); --记录条数
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''YYYY-MM-DD''';
  O_ERRCODE := 0;
  O_ERRMSG  := '运行成功';

  EXECUTE IMMEDIATE 'truncate table MDM_OBJ_TREE';
  insert into MDM_OBJ_TREE(F_NODE_ID, F_PARENT_ID, VC_NODE_NAME, VC_ISOBJ, F_OBJ_ID, VC_OBJ_TYPE, VC_OBJ_NAME_ZH, F_ORDER)
--用户
select
      a.vc_owner_type as f_node_id,
      '#' as f_parent_id,
      a.vc_owner as vc_node_name,
      '0'  vc_isobj,
      null f_obj_id,
      null vc_obj_type,
      NULL VC_OBJ_NAME_ZH,
      a.f_id f_order
     from mdm_owner a
--大类
union all
select
      ab.vc_owner_type||ac.vc_code f_node_id,
      ab.vc_owner_type f_parent_id,
      ac.vc_name vc_node_name,
      '0' vc_isobj,
      null f_obj_id,
      null vc_obj_type,
      NULL VC_OBJ_NAME_ZH,
      ac.f_id f_order
from mdm_owner ab,mdm_tree_alias ac

--一级分组
union all
select
      distinct
      to_char(nvl(b.f_group_id_merge,b.f_group_id)),
      (select vc_owner_type||'TABLE' from  mdm_owner z where  z.vc_owner=b.vc_owner),
      b.vc_group_name,
      '0' vc_isobj,
      null,
      null,
      NULL,
      b.f_order f_order
from mdm_obj_group b,mdm_owner ba
where b.vc_owner=ba.vc_owner
and b.f_group_pid=0

--其他分组
union all
select
      distinct
      to_char(nvl(b.f_group_id_merge,b.f_group_id)),
      to_char(b.f_group_pid),
      b.vc_group_name,
      '0' vc_isobj,
      null,
      null,
      NULL,
      b.f_order f_order
from mdm_obj_group b,mdm_owner ba
where b.vc_owner=ba.vc_owner
and b.f_group_pid!=0

--明细（已识别分组的）
UNION ALL
SELECT
      TO_CHAR(C.F_OBJ_ID) f_node_id,
      to_char(nvl(b.f_group_id_merge,b.f_group_id)) f_parent_id,
      C.VC_OBJ_NAME vc_node_name,
      '1' vc_isobj,
      C.F_OBJ_ID f_obj_id,
      c.vc_obj_type vc_obj_type,
      c.vc_obj_name_zh,
      30000 f_order
FROM MDM_OBJECT C,mdm_obj_group b
WHERE C.F_GROUP_ID IS NOT NULL
and c.vc_isshow='1'
and c.f_group_id=b.f_group_id
--明细（未识别分组的）
union all
SELECT
      TO_CHAR(C.F_OBJ_ID),
      D.VC_OWNER_TYPE||C.VC_OBJ_TYPE,
      C.VC_OBJ_NAME,
      '1',
      C.F_OBJ_ID,
      c.vc_obj_type,
      c.vc_obj_name_zh,
      40000 f_order
FROM MDM_OBJECT C,MDM_OWNER D
WHERE C.VC_OWNER=D.VC_OWNER
and c.vc_isshow='1'
AND C.F_GROUP_ID IS NULL;


EXCEPTION
  WHEN OTHERS THEN
    O_ERRCODE := SQLCODE;
    O_ERRMSG  := SUBSTR('未处理异常:' || SQLERRM || '。' ||
                        DBMS_UTILITY.FORMAT_ERROR_BACKTRACE,
                        1,
                        1000);

END P_MDM_OBJ_TREE;
```