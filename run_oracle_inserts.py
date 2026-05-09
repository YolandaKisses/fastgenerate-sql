#!/usr/bin/env python3
"""
执行 SQL_DIR 目录下所有 .sql 文件中的 INSERT 语句到 Oracle 数据库。

依赖安装：pip3 install oracledb
（使用 thin 模式，无需安装 Oracle Instant Client）

用法：
  python3 run_oracle_inserts.py           # 执行所有 .sql 文件
  python3 run_oracle_inserts.py --dry-run  # 仅打印不执行
  python3 run_oracle_inserts.py SYS_USER  # 只执行匹配 SYS_USER 的文件
"""


import os
import re
import sys
import argparse

import oracledb

# Oracle Thick Mode 初始化 (解决 DPY-3015 验证器不支持的问题)
ORACLE_CLIENT_PATH = "/Users/yolanda/opt/oracle/instantclient_23_26"
try:
    if os.path.exists(ORACLE_CLIENT_PATH):
        oracledb.init_oracle_client(lib_dir=ORACLE_CLIENT_PATH)
        print(f"✅ Oracle Thick Mode initialized using: {ORACLE_CLIENT_PATH}")
except Exception as e:
    print(f"⚠️ Failed to initialize Oracle Thick Mode: {e}")

DB_CONFIG = {

    "host": "192.168.1.206",
    "port": 1521,
    "service_name": "orclpdb",
    "user": "SID_PPAS_COM_SIT",
    "password": "SID_PPAS_COM_SIT",
}

# SQL 文件所在目录
SQL_DIR = "/Users/yolanda/Downloads/ppas sys表数据"


# 按依赖关系排序，避免外键约束报错（先插入主表，再插入子表）
FILE_ORDER = [
    "SYS_DEPT",
    "SYS_USER",
    "SYS_USER_DEPT",
    "SYS_USER_COMPANY",
    "SYS_USER_SETTING",
    "SYS_UPDATE_PWD",
    "SYS_ROLE",
    "SYS_USER_ROLE",
    "SYS_ACTION",
    "SYS_ROLE_ACTION",
    "SYS_APP_CONFIG",
    "SYS_DB_SOURCE",
    "SYS_SESSION",
    "SYS_TOKEN",
    "SYS_MSG",
    "SYS_USER_FUND",
    "SYS_USER_FUND_DETAIL",
    "SYS_USER_FUND_TREE",
]


def parse_inserts(sql_content):
    """解析 SQL 内容，提取每条 INSERT 语句。"""
    statements = []
    # 按 ; 后跟换行或文件结尾分割
    raw_stmts = re.split(r';\s*\n|;$', sql_content)
    for stmt in raw_stmts:
        stmt = stmt.strip()
        if stmt.upper().startswith("INSERT"):
            statements.append(stmt)
    return statements


def split_multi_insert(stmt):
    """将 Oracle 不支持的多行 VALUES 语法拆分为多条单行语句。"""
    # 匹配 "INSERT INTO ... VALUES" 部分
    match = re.match(r'(INSERT\s+INTO\s+.*?\s+VALUES)\s*(.*)', stmt, re.I | re.S)
    if not match:
        return [stmt]

    header = match.group(1)
    values_part = match.group(2).strip()

    # 拆分逻辑：寻找 ), 和 ( 之间的逗号作为行分隔符
    # 使用正则表达式分割：在 ) 之后、( 之前的逗号处拆分
    rows = re.split(r'(?<=\)),\s*(?=\()', values_part, flags=re.S)

    return [f"{header} {row.strip()}" for row in rows if row.strip()]


def execute_sql_file(cursor, filepath, dry_run=False):
    """执行单个 .sql 文件中的所有 INSERT 语句。"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    inserts = parse_inserts(content)
    if not inserts:
        print(f"  [跳过] 未找到 INSERT 语句")
        return 0

    success = 0
    errors = 0
    
    # 展开多行插入语句
    all_stmts = []
    for stmt in inserts:
        all_stmts.extend(split_multi_insert(stmt))
    
    print(f"  解析出 {len(all_stmts)} 条 SQL 语句...")

    for i, stmt in enumerate(all_stmts, 1):
        if dry_run:
            if i <= 3:  # 仅预览前几条
                preview = stmt[:120].replace("\n", " ").replace("\t", " ")
                print(f"  [{i}] {preview}...")
            elif i == 4:
                print(f"  ... 还有 {len(all_stmts)-3} 条语句 ...")
            success += 1
            continue

        try:
            cursor.execute(stmt)
            success += 1
        except Exception as e:
            errors += 1
            # 只在错误较少时详细打印，避免刷屏
            if errors <= 20:
                preview = stmt[:200].replace("\n", " ").replace("\t", " ")
                print(f"  [错误 #{i}] {e}")
                print(f"    SQL: {preview}...")
            elif errors == 21:
                print("  [提示] 错误较多，后续错误仅统计总数...")

    if not dry_run:
        print(f"  完成 -> 成功: {success}, 失败: {errors}")
    return errors


def get_sorted_sql_files(pattern=None):
    """获取指定目录下排序后的 .sql 文件列表。"""
    files = [f for f in os.listdir(SQL_DIR) if f.endswith(".sql")]
    if pattern:
        files = [f for f in files if pattern.upper() in f.upper()]

    # 按 FILE_ORDER 中定义的顺序排列，未在列表中的排最后
    ordered = []
    for prefix in FILE_ORDER:
        for f in sorted(files):
            if f.startswith(prefix) and f not in ordered:
                ordered.append(f)
    for f in sorted(files):
        if f not in ordered:
            ordered.append(f)
    return ordered


def main():
    parser = argparse.ArgumentParser(description="执行 Oracle 数据库 INSERT 脚本")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不执行")
    parser.add_argument("pattern", nargs="?", help="可选的 SQL 文件名匹配模式")
    args = parser.parse_args()

    sql_files = get_sorted_sql_files(args.pattern)
    if not sql_files:
        print("未找到 .sql 文件")
        return

    print(f"找到 {len(sql_files)} 个 SQL 文件")
    if args.dry_run:
        print("[DRY RUN 模式] 仅预览，不实际执行\n")

    dsn = oracledb.makedsn(DB_CONFIG["host"], DB_CONFIG["port"], service_name=DB_CONFIG["service_name"])
    conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"], dsn=dsn)
    print(f"已连接: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['service_name']}\n")

    total_errors = 0
    try:
        with conn.cursor() as cursor:
            for fname in sql_files:
                filepath = os.path.join(SQL_DIR, fname)
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                print(f"[{fname}] ({size_mb:.1f}MB)")
                total_errors += execute_sql_file(cursor, filepath, dry_run=args.dry_run)
                print()

            if not args.dry_run:
                conn.commit()
                print("=" * 50)
                print(f"✅ 全部提交完成。错误总数: {total_errors}")
            else:
                print("=" * 50)
                print(f"预览完成（未实际执行）。共 {len(sql_files)} 个文件。")
    except Exception as e:
        if 'conn' in locals() and conn:
            try:
                conn.rollback()
                print(f"⚠️ 执行失败，已回滚: {e}")
            except:
                print(f"⚠️ 执行失败且无法回滚: {e}")
        else:
            print(f"❌ 连接失败: {e}")
        # 如果是 ModuleNotFoundError，给出友好的提示
        if isinstance(e, NameError) and 'oracledb' in str(e):
            print("\n提示: 未找到 'oracledb' 模块。请确保在虚拟环境中运行，或者执行: pip install oracledb")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
        
        # 防止终端闪退
        print("\n" + "-"*30)
        input("按回车键退出...")


if __name__ == "__main__":
    main()
