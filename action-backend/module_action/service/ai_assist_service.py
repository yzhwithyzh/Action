"""
第四步「AI 辅助撰写」的模型调用层。

提示词怎么拼在 `report_assist_prompt`（纯函数）；这里只管**拿到能用的模型、把请求发出去、
出错就换下一个**。

## 为什么是同步接口，不是 Redis 队列 worker

仓库里另外两个 AI 工具（`tools/srd_worker_tool` / `tools/checklist_worker_tool`）都是
Redis 队列 + 常驻 worker，因为它们是**几分钟级**的任务：一次 SRD 评估几十次模型调用，
一次全稿校验要通读几万字。续写和润色不是 —— 用户敲完关键词等的是**秒级**返回。
照抄那套骨架会把体验变成「提交 → 排队 → 轮询」，比直接同步调用差得多，
而且要为一条几百字的改写多养一个进程。

代价是这个接口会占着一个 worker 线程若干秒，所以有超时（`_TIMEOUT_SECONDS`）
和输入长度上限（VO 的 `MAX_ASSIST_INPUT_CHARS`）兜着。

## 为什么手写 httpx 而不用 agno 的 Agent

`module_ai` 的对话走 agno `Agent`，那套东西带会话存储、历史注入、流式事件 —— 是为
多轮对话设计的。这里要的是一次性的 completion，没有会话、没有历史、不流式。
用 httpx 直接打 OpenAI 兼容的 `/chat/completions`，与仓库对 OSS、DirectMail
的处理是同一个取舍（`utils/oss_util.py` 手写签名而不引 oss2）。

## 模型池：顺序轮询 + 出错切换

`AiModelService.get_usable_ai_model_pool_services` 返回的是按 `model_sort` 排好的池子。
逐个试，撞到限流/欠费/鉴权失败就换下一个。**不做跨进程冻结** —— 那是 worker 那边
（`tools/common`）为几分钟一次的任务做的优化，这里一次调用几秒，冻结表的维护成本
高于收益；池子空了或全挂了就如实报错，不静默返回空串。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from exceptions.exception import ServiceException
from module_action.service.report_assist_prompt import AssistContext, build_messages
from module_ai.service.ai_model_service import AiModelService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: 单次调用的超时。用户在页面上等着，超过这个数不如让他重试
_TIMEOUT_SECONDS = 45.0
#: 输出上限。一条 checklist 应答不该长过这个数，给多了只是烧钱
_MAX_OUTPUT_TOKENS = 1200
#: 改写要的是稳定输出，不是创意
_TEMPERATURE = 0.3
#: OpenAI 兼容端点的默认地址，模型没配 base_url 时用
_DEFAULT_BASE_URL = 'https://api.openai.com/v1'


def _endpoint(base_url: str | None) -> str:
    """
    把模型配置里的 base_url 拼成 chat/completions 的完整地址

    库里存的可能是 `https://x/v1`，也可能已经带了 `/chat/completions`，两种都容得下。

    :param base_url: 模型配置里的地址
    :return: 完整端点
    """
    url = (base_url or _DEFAULT_BASE_URL).strip().rstrip('/')

    return url if url.endswith('/chat/completions') else f'{url}/chat/completions'


def _extract_text(payload: dict[str, Any]) -> str:
    """
    从 OpenAI 兼容响应里取出正文

    :param payload: 响应 JSON
    :return: 正文，取不到时空串
    """
    choices = payload.get('choices') or []
    if not choices:
        return ''
    message = (choices[0] or {}).get('message') or {}

    return (message.get('content') or '').strip()


class AiAssistService:
    """
    第四步的改写服务
    """

    @classmethod
    async def _call_one(cls, model: Any, messages: list[dict]) -> str:
        """
        用某一个模型发一次请求

        :param model: 模型配置（api_key 已解密）
        :param messages: 消息列表
        :return: 改写后的正文
        :raises httpx.HTTPError: 网络层或 HTTP 状态失败，由调用方决定要不要换下一个
        """
        body = {
            'model': model.model_code,
            'messages': messages,
            'temperature': _TEMPERATURE,
            'max_tokens': min(_MAX_OUTPUT_TOKENS, model.max_tokens or _MAX_OUTPUT_TOKENS),
            'stream': False,
        }
        headers = {'Authorization': f'Bearer {model.api_key}', 'Content-Type': 'application/json'}
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.post(_endpoint(model.base_url), json=body, headers=headers)
            resp.raise_for_status()

            return _extract_text(resp.json())

    @classmethod
    async def rewrite(
        cls,
        query_db: AsyncSession,
        *,
        action: str,
        ctx: AssistContext,
        style: str = '',
        keywords: str = '',
        locale: str = 'zh',
    ) -> tuple[str, str]:
        """
        跑一次续写 / 润色 / 中译英

        :param query_db: orm对象
        :param action: continue / polish / translate
        :param ctx: 条目上下文
        :param style: 润色风格
        :param keywords: 续写关键词
        :param locale: 界面语言
        :return: (改写后的正文, 出结果的模型标识)
        :raises ServiceException: 池子是空的，或池里所有模型都失败了
        """
        pool = await AiModelService.get_usable_ai_model_pool_services(query_db)
        pool = [m for m in pool if m.model_code and m.api_key]
        if not pool:
            # 如实报错，不静默返回空串 —— 后者会让用户以为「AI 觉得没什么好改的」
            raise ServiceException(message='暂无可用的AI模型，请联系管理员在「AI模型管理」中配置')

        messages = build_messages(action, ctx, style=style, keywords=keywords, locale=locale)
        last_error = ''
        for model in pool:
            label = f'{model.provider}/{model.model_code}#{model.model_id}'
            try:
                text = await cls._call_one(model, messages)
            except httpx.HTTPStatusError as e:
                # 限流 / 欠费 / 鉴权失败：这个模型这会儿用不了，换下一个
                last_error = f'HTTP {e.response.status_code}'
                logger.warning('模型 %s 调用失败(%s)，切换下一个', label, last_error)
                continue
            except httpx.HTTPError as e:
                last_error = type(e).__name__
                logger.warning('模型 %s 网络失败(%s)，切换下一个', label, last_error)
                continue

            if text:
                return text, label
            # 返回了但正文是空的：模型没拒答也没干活，同样算这一个不可用
            last_error = '返回内容为空'
            logger.warning('模型 %s 返回空内容，切换下一个', label)

        raise ServiceException(message=f'AI 改写失败，已尝试 {len(pool)} 个模型（最后一次：{last_error}）')
