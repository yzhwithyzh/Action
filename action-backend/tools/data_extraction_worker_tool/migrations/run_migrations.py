#!/usr/bin/env python3
"""
数据抽取 Worker 数据库迁移脚本

用法:
    python run_migrations.py
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

# 添加后端目录到路径
backend_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))

from config.env import DataBaseConfig


def get_database_url():
    """获取数据库连接 URL"""
    return (
        f'mysql+pymysql://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
        f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
    )


def run_migration():
    """执行数据库迁移"""
    # 获取 SQL 文件路径
    migrations_dir = Path(__file__).parent
    sql_file = migrations_dir / 'create_tables.sql'

    if not sql_file.exists():
        print(f"✗ 迁移文件不存在: {sql_file}")
        return False

    print(f"数据抽取 Worker 数据库迁移")
    print(f"{'='*60}")

    # 创建数据库连接
    try:
        database_url = get_database_url()
        engine = create_engine(database_url)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT DATABASE()"))
            db_name = result.fetchone()[0]
            print(f"✓ 已连接到数据库: {db_name}")
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return False

    # 读取并执行 SQL
    print(f"\n执行迁移文件: {sql_file.name}")
    print(f"{'='*60}")

    try:
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 分割 SQL 语句
        statements = []
        for line in sql_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('--'):
                statements.append(line)

        sql_combined = ' '.join(statements)
        statements = [s.strip() for s in sql_combined.split(';') if s.strip()]

        # 执行每条语句
        with engine.connect() as conn:
            for i, statement in enumerate(statements, 1):
                try:
                    # 显示正在执行的语句（截取前80字符）
                    display_stmt = statement[:80] + '...' if len(statement) > 80 else statement
                    print(f"\n[{i}/{len(statements)}] {display_stmt}")

                    conn.execute(text(statement))
                    conn.commit()
                    print(f"  ✓ 成功")

                except Exception as e:
                    error_msg = str(e)

                    # 忽略已存在的错误
                    if any(x in error_msg for x in [
                        "Duplicate column name",
                        "Duplicate key name",
                        "Duplicate entry",
                        "already exists"
                    ]):
                        print(f"  ⚠ 已存在，跳过")
                        continue
                    else:
                        print(f"  ✗ 失败: {error_msg}")
                        raise

        print(f"\n{'='*60}")
        print("✓ 迁移完成!")
        print(f"{'='*60}\n")
        return True

    except Exception as e:
        print(f"\n✗ 迁移失败: {e}")
        return False


if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
