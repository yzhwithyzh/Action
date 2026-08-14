"""投递端命令行 —— 不开浏览器也能跑通整条链路，`status_checklist_worker.sh` 也靠它查队列。

    python -m tools.checklist_worker_tool.cli submit draft.txt --guideline STRICTA
    python -m tools.checklist_worker_tool.cli submit - --guideline CARE      # 从 stdin 读稿件
    python -m tools.checklist_worker_tool.cli status <session_id>
    python -m tools.checklist_worker_tool.cli logs   <session_id> -f
    python -m tools.checklist_worker_tool.cli stop   <session_id>
    python -m tools.checklist_worker_tool.cli queue

`--guideline` 是 `action_guideline.code`（STRICTA / CARE / PRISMA / SPIRIT / RIGHT / ARRIVE）。
模型不在这里指定，worker 从 `ai_models` 表取池子；`--model-ids` 只是把范围缩小到其中几个。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.checklist_worker_tool.config.worker_config import CONFIG
from tools.common.bootstrap import configure_console
from tools.common.task_client import TaskClient

#: 与 worker 的 MIN_MANUSCRIPT_CHARS、后端 VO 的 min_length 对齐。
#: 在这里先拦一道，省得排队几分钟才被 worker 判成 payload 非法。
MIN_MANUSCRIPT_CHARS = 200


def _read_manuscript(source: str) -> str:
    """从文件或 stdin 读稿件。稿件不落库、不落盘，只在队列与 worker 进程里流转。"""
    text = sys.stdin.read() if source == '-' else Path(source).read_text(encoding='utf-8')
    text = text.strip()
    if len(text) < MIN_MANUSCRIPT_CHARS:
        raise SystemExit(f'稿件过短（{len(text)} 字，至少 {MIN_MANUSCRIPT_CHARS} 字），不投递')

    return text


async def cmd_submit(args: argparse.Namespace) -> int:
    payload: dict[str, object] = {
        'user_id': args.user_id,
        'guideline_code': args.guideline,
        'manuscript': _read_manuscript(args.manuscript),
        'locale': args.locale,
        'engine': {
            'batch_size': args.batch_size,
            'max_concurrency': args.concurrency,
            'consistency': {'max_chars': args.consistency_chars},
        },
    }
    if args.model_ids:
        payload['model_ids'] = [int(x) for x in args.model_ids.split(',') if x.strip().isdigit()]

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
    p = argparse.ArgumentParser(prog='checklist-worker-cli', description='报告规范校验 worker 投递端')
    sub = p.add_subparsers(dest='cmd', required=True)

    sp = sub.add_parser('submit', help='投递一次「稿件 × 规范」校验')
    sp.add_argument('manuscript', help='稿件文件路径；用 - 表示从 stdin 读')
    sp.add_argument('--guideline', required=True, help='规范代号，如 STRICTA / CARE / PRISMA')
    sp.add_argument('--locale', choices=['zh', 'en'], default='zh', help='条目与结论使用的语言')
    sp.add_argument('--user-id', type=int, default=0)
    sp.add_argument('--session-id', default='')
    sp.add_argument('--model-ids', default='', help='只用 ai_models 里的这几个模型，逗号分隔')
    sp.add_argument('--batch-size', type=int, default=8, help='每次请求塞几条条目')
    sp.add_argument('--concurrency', type=int, default=4, help='逐条判定的并发请求数')
    sp.add_argument('--consistency-chars', type=int, default=60000, help='全稿校验的通读字符预算')
    sp.set_defaults(func=cmd_submit)

    sp = sub.add_parser('status', help='查任务状态（完成后 result 里带逐条判定与全稿校验）')
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
