"""命令行入口 —— 脱离后端与数据库独立运行，供方法学专家离线批量验证。

    srd checklist                      查看 34 条目清单（不调模型）
    srd criteria 2b                    查看某条目的评分锚点
    srd aggregate ratings.json         由条目评分直接算领域/整体（不调模型）
    srd parse a.pdf                    看解析出的章节结构
    srd extract a.pdf -o a.facet.json  只跑单篇抽取
    srd assess a.pdf b.pdf -o r.json   完整评估
    srd report r.json -v               渲染已有结果
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

from srd_engine import pdf as pdf_util
from srd_engine.adapters.langchain_client import LlmRunner
from srd_engine.aggregate import from_rating_map, from_verdict_map
from srd_engine.checklist import ALL_ITEMS, DOMAINS, criteria_of
from srd_engine.config import EngineConfig, ModelConfig, model_config_from_env
from srd_engine.extract import extract_doc
from srd_engine.report import render_text, to_csv
from srd_engine.schemas import AssessmentResult, ExtractDoc


def _progress(stage: str, done: int, total: int, detail: str) -> None:
    print(f'[{stage}] {done}/{total} {detail}', file=sys.stderr, flush=True)


def _engine_cfg(args: argparse.Namespace) -> EngineConfig:
    return EngineConfig(
        extract_scope=args.extract_scope,
        judge_granularity=args.granularity,
        max_concurrency=args.concurrency,
    )


def _model_cfg(args: argparse.Namespace) -> ModelConfig:
    """从环境变量取模型配置，命令行只覆盖 provider / model。

    必须用 `replace` 而不是重建 —— 旧实现手工列字段，漏掉了 `context_window`、
    `timeout`、`extra`，导致只要命令行带 `--model`（README 示例里的常见用法），
    `context_window` 就回落到 0，分块与裁决整条链路静默失效（评审 P3）。
    """
    cfg = model_config_from_env()
    overrides = {}
    if args.provider:
        overrides['provider'] = args.provider
    if args.model:
        overrides['model'] = args.model
    if overrides:
        cfg = replace(cfg, **overrides)
    if not cfg.api_key:
        print('警告：未设置 API key（SRD_API_KEY 或 OPENAI_API_KEY）', file=sys.stderr)
    return cfg


# --------------------------------------------------------------------------- 子命令


def cmd_checklist(args: argparse.Namespace) -> int:
    for d in DOMAINS:
        tag = '【关键】' if d.is_key else '　　　　'
        print(f'\n{tag} {d.name_zh}  ({len(d.items)} 条)')
        for g in d.groups:
            print(f'  {g.code}. {g.name_zh}')
            for it in g.items:
                mode = ' [主观]' if it.judge_mode == 'debate' else ''
                card = ' [证据卡]' if it.has_evidence_card else ''
                print(f'    {it.code:<4} {it.question_zh}{mode}{card}')
    print(f'\n合计 {len(ALL_ITEMS)} 条目')
    return 0


def cmd_criteria(args: argparse.Namespace) -> int:
    c = criteria_of(args.code)
    label = {'dup_when': '3 分锚点（完全相同）', 'diff_when': '0 分锚点（完全不同）',
             'unclear_when': 'unclear（证据不足）', 'score_note': '中间档提示', 'note': '补充说明'}
    print(f'条目 {args.code}')
    for key, title in label.items():
        if c.get(key):
            print(f'\n[{title}]\n{c[key].strip()}')
    print('\n[2 分 / 1 分]\n两个锚点之间按「差异会不会改变临床或方法学解读」取档，通用口径见 prompts.py')
    return 0


def cmd_aggregate(args: argparse.Namespace) -> int:
    """输入既收新的评分表，也收 0.6.0 的 dup/diff 老文件 —— 存量结果还得能复算。"""
    mapping = json.loads(Path(args.verdicts).read_text(encoding='utf-8'))
    legacy = any(str(v) in ('dup', 'diff') for v in mapping.values())
    result = from_verdict_map(mapping) if legacy else from_rating_map(mapping)
    if legacy:
        print('输入是 0.6.0 的 dup/diff 老格式：dup 按 3 分、diff 按 0 分折算', file=sys.stderr)
    print(render_text(result, verbose=args.verbose))
    if args.out:
        Path(args.out).write_text(result.model_dump_json(indent=2), encoding='utf-8')
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    doc = pdf_util.parse(args.file)
    print(f'{doc.source}\nsha256={doc.sha256[:16]}  页数={doc.page_count}  章节={len(doc.sections)}')
    for s in doc.sections:
        print(f'  p.{s.page_from}-{s.page_to}  {s.title[:60]}  ({len(s.text)} 字符)')
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    doc = pdf_util.parse(args.file)
    runner = LlmRunner(_model_cfg(args), max_concurrency=args.concurrency)
    cfg = _engine_cfg(args)
    extract, warnings = asyncio.run(
        extract_doc(runner, doc, title=args.title, cfg=cfg)
    )
    out = Path(args.out) if args.out else Path(args.file).with_suffix('.facet.json')
    out.write_text(extract.model_dump_json(indent=2), encoding='utf-8')
    print(f'已写出 {out}', file=sys.stderr)
    for w in warnings:
        print(f'  ⚠ {w}', file=sys.stderr)
    print(f'调用 {runner.calls} 次，token 入 {runner.token_in} / 出 {runner.token_out}', file=sys.stderr)
    return 0


def cmd_assess(args: argparse.Namespace) -> int:
    from srd_engine.pipeline import assess, assess_from_extracts  # noqa: PLC0415

    cfg = _engine_cfg(args)
    model_cfg = _model_cfg(args)

    if args.a.endswith('.facet.json') and args.b.endswith('.facet.json'):
        ea = ExtractDoc.model_validate_json(Path(args.a).read_text(encoding='utf-8'))
        eb = ExtractDoc.model_validate_json(Path(args.b).read_text(encoding='utf-8'))
        runner = LlmRunner(model_cfg, max_concurrency=cfg.max_concurrency)
        result = asyncio.run(assess_from_extracts(runner, ea, eb, cfg, on_progress=_progress))
    else:
        result = asyncio.run(
            assess(args.a, args.b, model_cfg, cfg, cache_dir=args.cache,
                   title_a=args.title_a, title_b=args.title_b, on_progress=_progress)
        )

    if args.out:
        Path(args.out).write_text(result.model_dump_json(indent=2), encoding='utf-8')
        print(f'已写出 {args.out}', file=sys.stderr)
    if args.csv:
        Path(args.csv).write_text(to_csv(result), encoding='utf-8-sig')
        print(f'已写出 {args.csv}', file=sys.stderr)
    print(render_text(result, verbose=args.verbose))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    result = AssessmentResult.model_validate_json(Path(args.result).read_text(encoding='utf-8'))
    print(render_text(result, verbose=args.verbose))
    if args.csv:
        Path(args.csv).write_text(to_csv(result), encoding='utf-8-sig')
    return 0


# --------------------------------------------------------------------------- 入口


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='srd', description='SRD 系统综述重复性评估引擎')
    sub = p.add_subparsers(dest='cmd', required=True)

    def add_model_opts(sp: argparse.ArgumentParser) -> None:
        sp.add_argument('--provider', default='', help='OpenAI / DeepSeek / Anthropic / Google …')
        sp.add_argument('--model', default='', help='模型名，覆盖 SRD_MODEL')
        sp.add_argument('--concurrency', type=int, default=8)
        sp.add_argument('--extract-scope', choices=['full', 'sections'], default='full',
                        help='抽取时喂全篇（默认）还是只喂命中的章节')
        sp.add_argument('--granularity', choices=['all', 'per_group', 'per_item'], default='all',
                        help='all=34 条一次调用（默认）/ per_group=12 次 / per_item=34 次')

    sp = sub.add_parser('checklist', help='查看 34 条目清单')
    sp.set_defaults(func=cmd_checklist)

    sp = sub.add_parser('criteria', help='查看某条目的判定口径')
    sp.add_argument('code')
    sp.set_defaults(func=cmd_criteria)

    sp = sub.add_parser('aggregate', help='由条目评分算领域/整体（不调模型）')
    sp.add_argument('verdicts', help='JSON：{"1a":"0","1b":"3",...}（也收 0.6.0 的 dup/diff 老格式）')
    sp.add_argument('-o', '--out', default='')
    sp.add_argument('-v', '--verbose', action='store_true')
    sp.set_defaults(func=cmd_aggregate)

    sp = sub.add_parser('parse', help='解析 PDF 看章节结构')
    sp.add_argument('file')
    sp.set_defaults(func=cmd_parse)

    sp = sub.add_parser('extract', help='单篇结构化抽取')
    sp.add_argument('file')
    sp.add_argument('-o', '--out', default='')
    sp.add_argument('--title', default='')
    add_model_opts(sp)
    sp.set_defaults(func=cmd_extract)

    sp = sub.add_parser('assess', help='完整评估两篇综述')
    sp.add_argument('a', help='综述A：PDF/TXT，或已抽好的 *.facet.json')
    sp.add_argument('b', help='综述B：PDF/TXT，或已抽好的 *.facet.json')
    sp.add_argument('-o', '--out', default='')
    sp.add_argument('--csv', default='')
    sp.add_argument('--cache', default='', help='抽取缓存目录')
    sp.add_argument('--title-a', default='')
    sp.add_argument('--title-b', default='')
    sp.add_argument('-v', '--verbose', action='store_true')
    add_model_opts(sp)
    sp.set_defaults(func=cmd_assess)

    sp = sub.add_parser('report', help='渲染已有结果 JSON')
    sp.add_argument('result')
    sp.add_argument('--csv', default='')
    sp.add_argument('-v', '--verbose', action='store_true')
    sp.set_defaults(func=cmd_report)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
