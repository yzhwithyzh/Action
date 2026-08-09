"""
把首页资源中心的六张组织标识图批量传到阿里云 OSS，并回写数据库与种子 SQL。

这批图最初随前端打包，放在 action-frontend/public/assets/ 下按站内相对路径
`/assets/logo-xxx.png` 引用。官网（SSG 静态站）自己读得到，但后台「资源中心管理」页
是另一个域，`<el-image src="/assets/logo-equator.png">` 会打到后台自己的源上 404
—— 列表里一片裂图。换成 OSS 公网地址后两端引用同一个地址，与团队头像同理
（见 tools/upload_team_avatars.py）。

用法（工作目录必须是 action-backend/）：
    python -m tools.upload_resource_logos            # 上传 + 回写 DB + 回写种子 SQL
    python -m tools.upload_resource_logos --dry-run  # 只看要传什么，不动 OSS 和库

前置：.env.dev 里配好 OSS_ENABLED / OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET。

**原文件保留不删**：action_news 里有 4 条新闻的 thumb_url 仍指向同一批
`/assets/logo-*.png`（CARE / CONSORT / PRISMA / ARRIVE 那几条领域新闻），
删掉会把首页新闻区的缩略图一起打没。本脚本只改 action_resource_link 这一张表。

对象键用文件名而不是随机串（`site/resource/logo-equator.png`）：这批是随代码走的
种子数据，键稳定才能让种子 SQL 里的 URL 可读、可重复执行。后台上传的新图仍走随机键
（见 OssUtil.build_object_key），避免同名覆盖悄悄换掉已被引用的图。
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import asyncpg
from config.env import DataBaseConfig, OssConfig
from utils.oss_util import OssUtil

LOGO_DIR = Path(__file__).resolve().parent.parent.parent / 'action-frontend' / 'public' / 'assets'
SEED_SQL = Path(__file__).resolve().parent.parent / 'sql' / 'action-resource-link-pg.sql'


async def main() -> None:
    parser = argparse.ArgumentParser(description='资源中心标识图上传 OSS')
    parser.add_argument('--dry-run', action='store_true', help='只打印计划，不实际上传与写库')
    parser.add_argument(
        '--force', action='store_true', help='匿名可读性自检不通过时仍然回写 DB 与种子 SQL（会让前台图裂）'
    )
    args = parser.parse_args()

    files = sorted(LOGO_DIR.glob('logo-*.png'))
    if not files:
        raise SystemExit(f'没有找到标识图文件，请确认目录：{LOGO_DIR}')

    if not args.dry_run and not OssUtil.is_configured():
        raise SystemExit('OSS 未配置：请先在 .env.dev 里填好 OSS_ENABLED / OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET')

    prefix = OssConfig.oss_dir_prefix.strip('/')
    mapping: dict[str, str] = {}
    for path in files:
        key = '/'.join([p for p in (prefix, 'resource', path.name) if p])
        url = OssUtil.public_url(key)
        mapping[f'/assets/{path.name}'] = url
        if args.dry_run:
            print(f'[dry-run] {path.name} -> {url}')
            continue
        await OssUtil.put_object(key, path.read_bytes(), 'png')
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

    # 回写种子 SQL：把 '/assets/logo-xxx.png' 换成 OSS 公网地址，保证重跑 SQL 得到同一份数据
    sql = SEED_SQL.read_text(encoding='utf-8')
    for old, new in mapping.items():
        sql = sql.replace(f"'{old}'", f"'{new}'")
    SEED_SQL.write_text(sql, encoding='utf-8', newline='\n')
    print(f'rewrote   {SEED_SQL.name}')

    # 回写数据库：只改还指向站内相对路径的行，后台已经换过的图不动
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
                'update action_resource_link set logo_url = $1 where logo_url = $2', new, old
            )
            print(f'db        {old} -> {new}  ({updated})')
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
