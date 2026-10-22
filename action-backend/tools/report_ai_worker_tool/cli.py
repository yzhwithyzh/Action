"""运维命令行 —— `status_report_ai_worker.sh` 靠它查队列，排障时查任务状态 / 日志 / 停止。

    python -m tools.report_ai_worker_tool.cli queue
    python -m tools.report_ai_worker_tool.cli status <session_id>
    python -m tools.report_ai_worker_tool.cli logs   <session_id> -f
    python -m tools.report_ai_worker_tool.cli stop   <session_id>

**没有 submit**：任务 payload 里的条目上下文由后端 `ReportAiService` 从草稿组出来，
手拼一份没有意义；要验证链路请在官网第四步点「一键优化」或「生成整篇」。
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
from tools.report_ai_worker_tool.config.worker_config import CONFIG


async def cmd_status(args: argparse.Namespace) -> int:
    """打印任务状态 JSON（与后端轮询接口读到的是同一份）"""
    async with TaskClient(CONFIG) as client:
        state = await client.status(args.session_id)
    if state is None:
        print('任务不存在（或已过期）', file=sys.stderr)
        return 1
    print(json.dumps(state, ensure_ascii=False, indent=2))

    return 0


async def cmd_logs(args: argparse.Namespace) -> int:
    """打印任务日志；`-f` 时实时跟随"""
    async with TaskClient(CONFIG) as client:
        if not args.follow:
            for record in await client.logs(args.session_id):
                print(f'{record.get("time", "")} [{record.get("level", "")}] {record.get("message", "")}')
            return 0
        async for record in client.subscribe_logs(args.session_id):
            print(f'{record.get("time", "")} [{record.get("level", "")}] {record.get("message", "")}', flush=True)

    return 0


async def cmd_stop(args: argparse.Namespace) -> int:
    """请求停止。一键优化停下时已经生成的建议照样会被后端落库"""
    async with TaskClient(CONFIG) as client:
        await client.stop(args.session_id)
    print(f'已请求停止，worker 最多 {CONFIG.stop_check_interval}s 后响应')

    return 0


async def cmd_queue(_: argparse.Namespace) -> int:
    """队列里还没被取走的任务数。一直不降多半是 worker 没起来，或后端与 worker 连的不是同一个队列"""
    async with TaskClient(CONFIG) as client:
        length = await client.queue_length()
    print(f'{CONFIG.queue_key}  待处理 {length} 个')

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='report-ai-worker-cli', description='报告助手 AI worker 运维命令')
    sub = p.add_subparsers(dest='cmd', required=True)
    for name, fn, help_ in (('status', cmd_status, '查任务状态'), ('stop', cmd_stop, '请求停止任务')):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument('session_id')
        sp.set_defaults(func=fn)
    sp = sub.add_parser('logs', help='查任务日志')
    sp.add_argument('session_id')
    sp.add_argument('-f', '--follow', action='store_true')
    sp.set_defaults(func=cmd_logs)
    sp = sub.add_parser('queue', help='查看队列长度')
    sp.set_defaults(func=cmd_queue)

    return p


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = build_parser().parse_args(argv)

    return asyncio.run(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main())
