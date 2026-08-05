"""
把团队成员头像批量传到阿里云 OSS，并回写数据库与种子 SQL。

头像最初是从《ACTION网站及其材料/About us/How we are organised(2).docx》里抽出来的，
一度放在 action-frontend/public/team/ 下按站内相对路径引用。改成 OSS 后：
  - 官网（SSG 静态站）与后台（另一个域）引用的是同一个公网地址，后台预览不再糊
  - 换机 / 多副本部署时图片不跟着后端机器走

用法（工作目录必须是 action-backend/）：
    python -m tools.upload_team_avatars            # 上传 + 回写 DB + 回写种子 SQL
    python -m tools.upload_team_avatars --dry-run  # 只看要传什么，不动 OSS 和库

前置：.env.dev 里配好 OSS_ENABLED / OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET。

对象键用文件名而不是随机串（`site/team/lin-shi.jpg`）：这批是随代码走的种子数据，
键稳定才能让种子 SQL 里的 URL 可读、可重复执行。后台上传的新头像仍走随机键，
避免同名覆盖悄悄换掉已被引用的图。
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import asyncpg
from config.env import DataBaseConfig, OssConfig
from utils.oss_util import OssUtil

AVATAR_DIR = Path(__file__).resolve().parent / 'team-avatars'
SEED_SQL = Path(__file__).resolve().parent.parent / 'sql' / 'action-team-pg.sql'


async def main() -> None:
    parser = argparse.ArgumentParser(description='团队成员头像上传 OSS')
    parser.add_argument('--dry-run', action='store_true', help='只打印计划，不实际上传与写库')
    parser.add_argument(
        '--force', action='store_true', help='匿名可读性自检不通过时仍然回写 DB 与种子 SQL（会让前台图裂）'
    )
    args = parser.parse_args()

    files = sorted(AVATAR_DIR.glob('*.jpg'))
    if not files:
        raise SystemExit(f'没有找到头像文件，请确认目录：{AVATAR_DIR}')

    if not args.dry_run and not OssUtil.is_configured():
        raise SystemExit('OSS 未配置：请先在 .env.dev 里填好 OSS_ENABLED / OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET')

    prefix = OssConfig.oss_dir_prefix.strip('/')
    mapping: dict[str, str] = {}
    for path in files:
        key = '/'.join([p for p in (prefix, 'team', path.name) if p])
        url = OssUtil.public_url(key)
        mapping[f'/team/{path.name}'] = url
        if args.dry_run:
            print(f'[dry-run] {path.name} -> {url}')
            continue
        await OssUtil.put_object(key, path.read_bytes(), 'jpg')
        print(f'uploaded  {path.name} -> {url}')

    if args.dry_run:
        return

    # 传上去了 ≠ 读得到。官网是预渲染静态站，<img src> 由匿名访客直接打 OSS；
    # 桶私有且没授公共读时上传会成功、页面却全是 403。所以回写前先真去匿名 GET 一次，
    # 不通过就保持库里的站内相对路径不动 —— 宁可维持现状，也不要把前台换成一片裂图。
    probe_url = next(iter(mapping.values()))
    if not await OssUtil.is_publicly_readable(probe_url):
        message = (
            f'匿名读取失败：{probe_url}\n'
            '文件已传上 OSS，但公网读不到。请在 OSS 控制台把桶 action-gmu 的读写权限设为「公共读」\n'
            '（或关掉「阻止公共访问」后把 OSS_OBJECT_ACL 设成 public-read），然后重跑本脚本。\n'
            '在此之前数据库与种子 SQL 保持站内相对路径不变，官网显示不受影响。'
        )
        if not args.force:
            raise SystemExit(message)
        print(f'[force] {message}')
    else:
        print(f'verified  匿名可读 {probe_url}')

    # 回写种子 SQL：把 '/team/xxx.jpg' 换成 OSS 公网地址，保证重跑 SQL 得到同一份数据
    sql = SEED_SQL.read_text(encoding='utf-8')
    for old, new in mapping.items():
        sql = sql.replace(f"'{old}'", f"'{new}'")
    SEED_SQL.write_text(sql, encoding='utf-8', newline='\n')
    print(f'rewrote   {SEED_SQL.name}')

    # 回写数据库：只改还指向站内相对路径的行，后台已经换过的头像不动
    conn = await asyncpg.connect(
        host=DataBaseConfig.db_host,
        port=DataBaseConfig.db_port,
        user=DataBaseConfig.db_username,
        password=DataBaseConfig.db_password,
        database=DataBaseConfig.db_database,
    )
    try:
        for old, new in mapping.items():
            updated = await conn.execute(
                'update action_team_member set avatar_url = $1 where avatar_url = $2', new, old
            )
            print(f'db        {old} -> {new}  ({updated})')
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
