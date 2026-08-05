"""投递端命令行 —— 后端接口写好之前，用它跑通整条链路。

    python -m tools.srd_worker_tool.cli submit a.pdf b.pdf              # 模型取自 ai_models 表
    python -m tools.srd_worker_tool.cli submit a.pdf b.pdf --model-ids 3,7  # 只用其中两个
    python -m tools.srd_worker_tool.cli status <session_id>
    python -m tools.srd_worker_tool.cli logs   <session_id> -f
    python -m tools.srd_worker_tool.cli stop   <session_id>
    python -m tools.srd_worker_tool.cli queue

a/b 既可以是本地路径，也可以是 http(s) URL。模型参数不传就走 worker 侧的 SRD_* 环境变量。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.common.bootstrap import configure_console
from tools.common.task_client import TaskClient
from tools.srd_worker_tool.config.worker_config import CONFIG


def _spec(value: str, title: str) -> dict[str, str]:
    key = 'url' if value.startswith(('http://', 'https://')) else 'path'
    spec = {key: value if key == 'url' else str(Path(value).resolve())}
    if title:
        spec['title'] = title
    return spec


async def cmd_submit(args: argparse.Namespace) -> int:
    payload: dict[str, object] = {
        'user_id': args.user_id,
        'review_a': _spec(args.a, args.title_a),
        'review_b': _spec(args.b, args.title_b),
        'engine': {
            'judge_granularity': args.granularity,
            'extract_scope': args.extract_scope,
            'max_concurrency': args.concurrency,
        },
        'options': {'force': args.force},
    }
    # 不传 --api-key 时模型来自 ai_models 表（--model-ids 可缩小范围）；
    # 传了 --api-key 就是一次性的临时模型，不查库也不轮换
    if args.model_ids:
        payload['model_ids'] = [int(x) for x in args.model_ids.split(',') if x.strip().isdigit()]
    model = {k: v for k, v in
             (('provider', args.provider), ('model', args.model), ('api_key', args.api_key),
              ('base_url', args.base_url)) if v}
    if model:
        payload['model'] = model

    async with TaskClient(CONFIG) as client:
        sid = await client.submit(payload, session_id=args.session_id)
    print(sid)
    return 0


async def cmd_status(args: argparse.Namespace) -> int:
    async with TaskClient(CONFIG) as client:
        state = await client.status(args.session_id)
    if state is None:
        print('任务不存在（或已过期）', file=sys.stderr)
        return 1
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


async def cmd_logs(args: argparse.Namespace) -> int:
    async with TaskClient(CONFIG) as client:
        if not args.follow:
            for record in await client.logs(args.session_id):
                print(f'{record.get("time", "")} [{record.get("level", "")}] {record.get("message", "")}')
            return 0
        async for record in client.subscribe_logs(args.session_id):
            print(f'{record.get("time", "")} [{record.get("level", "")}] {record.get("message", "")}', flush=True)
    return 0


async def cmd_stop(args: argparse.Namespace) -> int:
    async with TaskClient(CONFIG) as client:
        await client.stop(args.session_id)
    print(f'已请求停止，worker 最多 {CONFIG.stop_check_interval}s 后响应')
    return 0


async def cmd_queue(_: argparse.Namespace) -> int:
    async with TaskClient(CONFIG) as client:
        length = await client.queue_length()
    print(f'{CONFIG.queue_key}  待处理 {length} 个')
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='srd-worker-cli', description='SRD worker 投递端')
    sub = p.add_subparsers(dest='cmd', required=True)

    sp = sub.add_parser('submit', help='投递一次 A/B 评估')
    sp.add_argument('a', help='综述A：本地路径或 URL')
    sp.add_argument('b', help='综述B：本地路径或 URL')
    sp.add_argument('--title-a', default='')
    sp.add_argument('--title-b', default='')
    sp.add_argument('--user-id', type=int, default=0)
    sp.add_argument('--session-id', default='')
    sp.add_argument('--model-ids', default='', help='只用 ai_models 里的这几个模型，逗号分隔')
    sp.add_argument('--provider', default='')
    sp.add_argument('--model', default='', help='仅在同时给了 --api-key（临时模型）时生效')
    sp.add_argument('--api-key', default='', help='给了就是一次性临时模型，不查 ai_models 表')
    sp.add_argument('--base-url', default='')
    sp.add_argument('--granularity', choices=['all', 'per_group', 'per_item'], default='all')
    sp.add_argument('--extract-scope', choices=['full', 'sections'], default='full')
    sp.add_argument('--concurrency', type=int, default=8)
    sp.add_argument('--force', action='store_true', help='忽略断点，强制重跑')
    sp.set_defaults(func=cmd_submit)

    sp = sub.add_parser('status', help='查任务状态')
    sp.add_argument('session_id')
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser('logs', help='查任务日志')
    sp.add_argument('session_id')
    sp.add_argument('-f', '--follow', action='store_true', help='实时跟随（等价于前端 SSE）')
    sp.set_defaults(func=cmd_logs)

    sp = sub.add_parser('stop', help='请求停止任务')
    sp.add_argument('session_id')
    sp.set_defaults(func=cmd_stop)

    sp = sub.add_parser('queue', help='查看队列长度')
    sp.set_defaults(func=cmd_queue)
    return p


def main(argv: list[str] | None = None) -> int:
    configure_console()  # 日志里带 ✓/▶ 等符号，Windows 的 GBK 控制台会直接崩
    args = build_parser().parse_args(argv)
    if args.cmd == 'submit' and not args.session_id:
        args.session_id = None
    return asyncio.run(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main())
