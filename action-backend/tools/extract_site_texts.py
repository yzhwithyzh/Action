"""把 action-frontend 的 i18n 词条抽成 action_site_text 的同步 SQL。

**可反复运行的同步脚本**，不是一次性导入：前端加了新词条、或改了某条默认文案，
重跑一次再执行生成的 SQL 即可，后台已经改过的那些不会被覆盖（见下面「同步语义」）。

用法（工作目录 action-backend/）：
    python -m tools.extract_site_texts            # 写 sql/action-site-text-pg.sql

同步语义（全在生成的 `on conflict do update` 里）：
  - 新键 → 插入，`text_* = default_*`（即「未改动」）
  - 老键 → 刷新 `default_*` / `page_key` / `sort_num` / `has_markup`
  - 老键且后台**没改过**（`text_* = 旧 default_*`）→ `text_*` 跟着新默认走
  - 老键且后台**改过** → `text_*` 原样保留

为什么要留 `default_*` 一列：公开接口只吐「与默认不同」的行。不存默认值就没法判断
「改没改过」，只能把 934 条整包塞进每个页面的 hydration payload（约 120KB），
而绝大多数时候一条都没被改过。存了默认值，没人改时公开接口返回空对象。

删键不在这里处理：前端删掉一个 i18n 键，库里那行会留着不再被引用，无害；
真要清就手工 delete，脚本不敢自动删（改错一次就是一段文案凭空消失）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCALE_DIR = REPO_ROOT / 'action-frontend' / 'i18n' / 'locales'
OUT_SQL = REPO_ROOT / 'action-backend' / 'sql' / 'action-site-text-pg.sql'

# 分组名：page_key（= 键的首段）→ 后台列表里显示的中文分组名。
# 键里没有的分段一律回落 page_key 本身，所以前端新增顶层分组不加在这里也不会出错。
PAGE_LABELS: dict[str, str] = {
    'brand': '品牌名称',
    'nav': '顶部导航',
    'footer': '页脚',
    'common': '通用',
    'auth': '登录注册',
    'index': '首页',
    'about': '关于我们',
    'assistant': '报告助手',
    'collaborate': '协作与联系',
    'guidelines': '报告规范目录',
    'guidelineDetail': '规范原文页',
    'implementation': '实施性研究',
    'news': '新闻动态',
    'newsDetail': '新闻详情',
    'team': '团队成员详情',
    'srd': 'SRD 重复性评估',
}


def _flatten(node: Any, prefix: str, out: dict[str, str]) -> None:
    """
    把嵌套的 i18n 对象拍平成 `a.b.c` → 文案

    :param node: 当前节点（dict 继续下钻，其余当叶子）
    :param prefix: 已累积的键前缀
    :param out: 结果字典（原地写入，保持 JSON 里的出现顺序）
    :return: None
    """
    if isinstance(node, dict):
        for key, value in node.items():
            _flatten(value, f'{prefix}.{key}' if prefix else key, out)

        return
    out[prefix] = '' if node is None else str(node)


def _quote(value: str | None) -> str:
    """
    转成 PostgreSQL 字符串字面量

    文案里含换行是常态（多段说明），Postgres 的单引号串本就允许跨行，无需转义。

    :param value: 原始文案
    :return: 可直接拼进 SQL 的字面量
    """
    if value is None:
        return 'null'

    return "'" + value.replace("'", "''") + "'"


def build_rows() -> list[dict[str, Any]]:
    """
    读取中英两份 locale JSON，拍平后按中文的键序对齐

    键序即 JSON 里的书写顺序，而它大体跟着页面从上到下走 —— 后台列表按 sort_num 排，
    读起来就和在官网上从上往下扫一遍差不多，比按字典序排的 `s001/s010/s100` 好找得多。

    :return: 待入库的行
    """
    zh_flat: dict[str, str] = {}
    en_flat: dict[str, str] = {}
    _flatten(json.loads((LOCALE_DIR / 'zh.json').read_text(encoding='utf-8')), '', zh_flat)
    _flatten(json.loads((LOCALE_DIR / 'en.json').read_text(encoding='utf-8')), '', en_flat)

    rows: list[dict[str, Any]] = []
    for index, (text_key, zh_text) in enumerate(zh_flat.items()):
        en_text = en_flat.get(text_key, '')
        page_key = text_key.split('.', 1)[0]
        rows.append(
            {
                'text_key': text_key,
                'page_key': page_key,
                'page_label': PAGE_LABELS.get(page_key, page_key),
                'text_zh': zh_text,
                'text_en': en_text,
                # 含尖括号的词条在前台是 v-html 渲染的（见 nuxt.config.ts 的 escapeHtml:false），
                # 后台据此给出「这条含标签，改动会进 v-html」的提示，写接口另有标签白名单校验
                'has_markup': '1' if ('<' in zh_text or '<' in en_text) else '0',
                'sort_num': index,
            }
        )

    # 只在英文里出现的键（中文漏配）也要入库，否则后台看不见、也就改不了
    for text_key, en_text in en_flat.items():
        if text_key in zh_flat:
            continue
        page_key = text_key.split('.', 1)[0]
        rows.append(
            {
                'text_key': text_key,
                'page_key': page_key,
                'page_label': PAGE_LABELS.get(page_key, page_key),
                'text_zh': '',
                'text_en': en_text,
                'has_markup': '1' if '<' in en_text else '0',
                'sort_num': len(rows),
            }
        )

    return rows


def render_sql(rows: list[dict[str, Any]]) -> str:
    """
    渲染完整的建表 + 同步 SQL

    :param rows: build_rows() 的结果
    :return: SQL 文本
    """
    values = ',\n'.join(
        '({text_key}, {page_key}, {page_label}, {text_zh}, {text_en}, {default_zh}, {default_en}, '
        '{has_markup}, {sort_num})'.format(
            text_key=_quote(row['text_key']),
            page_key=_quote(row['page_key']),
            page_label=_quote(row['page_label']),
            text_zh=_quote(row['text_zh']),
            text_en=_quote(row['text_en']),
            default_zh=_quote(row['text_zh']),
            default_en=_quote(row['text_en']),
            has_markup=_quote(row['has_markup']),
            sort_num=row['sort_num'],
        )
        for row in rows
    )

    return HEADER + values + TAIL.format(count=len(rows))


HEADER = """-- ----------------------------
-- 官网站点文案（PostgreSQL）
--
-- **本文件由 `python -m tools.extract_site_texts` 生成，不要手改。**
-- 数据源是 action-frontend/i18n/locales/{zh,en}.json，改默认文案请改那两份 JSON 后重跑；
-- 改**线上生效**的文案请走后台「站点文案管理」页面（那改的是 text_zh/text_en，不是这里）。
--
-- 为什么要有这张表：官网原本 934 条版面文案（标题/导语/正文段落/按钮字）全写死在 i18n JSON 里，
-- 甲方改一个字就要改代码 + 重新 `npm run generate`。表把这批文案搬进库，后台可改，
-- 前台通过 `GET /action/site/texts` 取覆盖项，在 i18n 之上 merge 一层。
--
-- 两列一组的含义（**别把它们看成中英两栏那种对称关系**）：
--   default_zh / default_en  代码里的原始文案，跟着前端 JSON 走，后台改不动
--   text_zh    / text_en     当前生效文案，后台改的是这两列
-- 公开接口只返回 `text_* <> default_*` 的行 —— 一条都没改时返回空对象，
-- 不给每个页面的 hydration payload 白白压上 120KB。「还原默认」就是把 text_* 写回 default_*。
--
-- 可重复执行：老键只刷新 default_*，后台改过的 text_* 原样保留（见文件末尾的 on conflict）。
-- ----------------------------

begin;

create table if not exists action_site_text (
    text_id     bigserial,
    text_key    varchar(128) not null,
    page_key    varchar(64)  not null default '',
    page_label  varchar(64)  not null default '',
    text_zh     text,
    text_en     text,
    default_zh  text,
    default_en  text,
    has_markup  char(1)      default '0',
    sort_num    int4         default 0,
    del_flag    char(1)      default '0',
    create_by   varchar(64)  default '',
    create_time timestamp(0),
    update_by   varchar(64)  default '',
    update_time timestamp(0),
    remark      varchar(500) default null,
    primary key (text_id)
);
comment on table  action_site_text is '官网-站点文案（i18n 词条的可编辑副本）';
comment on column action_site_text.text_key is 'i18n 键，如 index.s052，与前端 $t() 的参数一字不差';
comment on column action_site_text.page_key is '所属分组（= text_key 首段），用于后台按页筛选';
comment on column action_site_text.page_label is '分组中文名，随生成脚本的 PAGE_LABELS 走';
comment on column action_site_text.text_zh is '当前生效的中文文案（后台可改）';
comment on column action_site_text.text_en is '当前生效的英文文案（后台可改）';
comment on column action_site_text.default_zh is '代码里的中文默认值，来自 i18n/locales/zh.json，后台只读';
comment on column action_site_text.default_en is '代码里的英文默认值，来自 i18n/locales/en.json，后台只读';
comment on column action_site_text.has_markup is '默认值里含 HTML 标签（0否 1是），前台以 v-html 渲染，改动受标签白名单约束';
comment on column action_site_text.sort_num is '显示顺序，按 JSON 书写顺序生成，大体等同页面从上到下';

-- text_key 是同步的唯一依据，必须唯一。带 del_flag 条件是为了「删了还能重新插同名键」。
create unique index if not exists uk_action_site_text_key
    on action_site_text (text_key) where del_flag = '0';

-- 按分组 + 顺序取列表是后台唯一的高频查询
create index if not exists idx_action_site_text_page
    on action_site_text (page_key, sort_num);

-- ----------------------------
-- 词条同步
-- ----------------------------
insert into action_site_text
    (text_key, page_key, page_label, text_zh, text_en, default_zh, default_en, has_markup, sort_num)
values
"""

TAIL = """
on conflict (text_key) where del_flag = '0' do update set
    page_key   = excluded.page_key,
    page_label = excluded.page_label,
    has_markup = excluded.has_markup,
    sort_num   = excluded.sort_num,
    -- 后台没改过（当前值 = 旧默认值）的行，跟着新默认值走；改过的原样保留。
    -- 少了这个 case，前端改一句默认文案后，所有未被人工覆盖的行都会突然「变成已改动」，
    -- 并把旧文案当作覆盖项吐给前台 —— 等于代码里的修改永远上不了线。
    text_zh = case when action_site_text.text_zh is not distinct from action_site_text.default_zh
                   then excluded.default_zh else action_site_text.text_zh end,
    text_en = case when action_site_text.text_en is not distinct from action_site_text.default_en
                   then excluded.default_en else action_site_text.text_en end,
    default_zh = excluded.default_zh,
    default_en = excluded.default_en;

commit;

-- 共 {count} 条词条
"""


def main() -> None:
    """
    生成 sql/action-site-text-pg.sql

    :return: None
    """
    rows = build_rows()
    OUT_SQL.write_text(render_sql(rows), encoding='utf-8')
    pages = sorted({row['page_key'] for row in rows})
    markup = sum(1 for row in rows if row['has_markup'] == '1')
    print(f'已写出 {OUT_SQL.relative_to(REPO_ROOT)}：{len(rows)} 条词条，{len(pages)} 个分组，{markup} 条含标签')
    print('分组：' + '  '.join(pages))


if __name__ == '__main__':
    main()
