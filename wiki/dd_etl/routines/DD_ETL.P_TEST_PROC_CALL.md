---
project: dd_etl
type: routine-note
status: active
created: 2026/05/11
updated: 2026/05/11
tags:
  - routine-note
related:
routine_type: PROCEDURE
---

# ⚙️ DD_ETL.P_TEST_PROC_CALL

[⬅️ 返回数据源总览](../index.md)

::: info 存储过程信息
- **所属 Schema**: `DD_ETL`
- **类型**: `PROCEDURE`
:::

---

## 🔗 相关表
*暂无*

---

## 📜 源码
```sql
PROCEDURE P_TEST_PROC_CALL(I_STARTDATE in varchar2,
                                            I_ENDDATE   in varchar2,
                                            aaa   in varchar2,
                                            bbb   in varchar2,
                                            ccc   in varchar2,
                                            O_ERRCODE   OUT INTEGER,
                                            O_ERRMSG    OUT VARCHAR2) IS
--  V_NUMBER NUMBER(10); --记录条数
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''YYYY-MM-DD''';
  O_ERRCODE := 0;
  O_ERRMSG  := '运行成功';

EXCEPTION
  WHEN OTHERS THEN
    O_ERRCODE := SQLCODE;
    O_ERRMSG  := SUBSTR('未处理异常:' || SQLERRM || '。' ||
                        DBMS_UTILITY.FORMAT_ERROR_BACKTRACE,
                        1,
                        1000);

END P_TEST_PROC_CALL;
```