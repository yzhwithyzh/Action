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
from utils.llm_thinking_util import thinking_off_params

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: 单次调用的默认超时。第四步的改写是**秒级交互**，用户在页面上等着，
#: 超过这个数不如让他重试。输出长度不确定的任务（PDF 元数据抽取）自己传更大的值 ——
#: 非流式调用是要等整段生成完的，输出越长等得越久
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

    `complete()` 是这一层唯一的对外能力（拿到能用的模型、把消息发出去、出错换下一个），
    `rewrite()` 只是「拼第四步的提示词再调它」。别的功能要用模型池时**复用 complete**，
    不要另抄一份轮询逻辑 —— 眼下 `publication_meta_service` 的 PDF 元数据抽取走的就是它。
    """

    @classmethod
    async def _call_one(
        cls, model: Any, messages: list[dict], max_tokens: int | None, temperature: float, timeout: float
    ) -> str:
        """
        用某一个模型发一次请求

        :param model: 模型配置（api_key 已解密）
        :param messages: 消息列表
        :param max_tokens: 输出上限；**传 None 就整个不下发这个参数**，由模型用自己的默认上限
        :param temperature: 采样温度
        :param timeout: 单次调用超时（秒）
        :return: 正文
        :raises httpx.HTTPError: 网络层或 HTTP 状态失败，由调用方决定要不要换下一个
        """
        body: dict[str, Any] = {
            'model': model.model_code,
            'messages': messages,
            'temperature': temperature,
            'stream': False,
        }
        if getattr(model, 'support_reasoning', 'N') != 'Y':
            # 「AI模型管理」里那一栏「支持推理」配成否，就**真的别让它思考**。
            # 注意这与 `module_ai/service/ai_chat_service.py` 对同一个字段的用法不同：
            # 那边只是「不把 reasoning_content 显示给前端」，模型照样思考、照样计费。
            # 这一层的活儿（改写、照抄元数据）没一件需要思维链：实测同一份 PDF，
            # 开思考 850 completion_tokens / 15.4 秒，关掉 364 / 10.2 秒，
            # **产出的 JSON 一字不差**。而且思维链正是当初撞截断的元凶 ——
            # 它先吃掉大半额度，正文写到一半就没了。
            #
            # 各厂商的开关不同名（火山方舟/DeepSeek 是 `thinking`，百炼 qwen 是 `enable_thinking`），
            # 按端点挑，见 `utils/llm_thinking_util`。仍有厂商不认时会 400，
            # 那时模型池会自动切下一个（`complete` 的 HTTPStatusError 分支）——
            # 池子里只有那一个不认识它的模型时才会真的失败，届时把这个模型的
            # 「支持推理」改成是即可绕开
            body.update(thinking_off_params(model.provider, model.base_url, model.model_code))
        if max_tokens is not None:
            # 「AI模型管理」里那一栏「最大输出」会把调用方要的额度再压低一道。
            # 输出长度不确定的任务（PDF 元数据抽取）就别下发这个参数 —— 截断的表现是
            # 「正文看着正常、最后一句没写完」，下游只报得出「JSON 无法解析」，
            # 谁都想不到根因是额度。踩过一次
            body['max_tokens'] = min(max_tokens, model.max_tokens or max_tokens)
        headers = {'Authorization': f'Bearer {model.api_key}', 'Content-Type': 'application/json'}
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(_endpoint(model.base_url), json=body, headers=headers)
            resp.raise_for_status()

            return _extract_text(resp.json())

    @classmethod
    async def complete(
        cls,
        query_db: AsyncSession,
        messages: list[dict],
        *,
        max_tokens: int | None = _MAX_OUTPUT_TOKENS,
        temperature: float = _TEMPERATURE,
        timeout: float = _TIMEOUT_SECONDS,
        failure_hint: str = 'AI 调用失败',
    ) -> tuple[str, str]:
        """
        用模型池跑一次 completion：顺序轮询、出错换下一个

        :param query_db: orm对象
        :param messages: OpenAI 兼容的消息列表
        :param max_tokens: 输出上限；**输出长度不确定的任务传 None**，不下发这个参数
        :param temperature: 采样温度
        :param timeout: 单次调用超时（秒）。**不限长的任务要一并调大**，
            否则等不到模型把整段写完就 ReadTimeout（踩过一次）
        :param failure_hint: 全部失败时报错文案的前半句
        :return: (正文, 出结果的模型标识)
        :raises ServiceException: 池子是空的，或池里所有模型都失败了
        """
        pool = await AiModelService.get_usable_ai_model_pool_services(query_db)
        pool = [m for m in pool if m.model_code and m.api_key]
        if not pool:
            # 如实报错，不静默返回空串 —— 后者会让用户以为「AI 觉得没什么好改的」
            raise ServiceException(message='暂无可用的AI模型，请联系管理员在「AI模型管理」中配置')

        last_error = ''
        for model in pool:
            label = f'{model.provider}/{model.model_code}#{model.model_id}'
            try:
                text = await cls._call_one(model, messages, max_tokens, temperature, timeout)
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

        raise ServiceException(message=f'{failure_hint}，已尝试 {len(pool)} 个模型（最后一次：{last_error}）')

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
        instruction: str = '',
    ) -> tuple[str, str]:
        """
        跑一次续写 / 润色 / 中译英

        :param query_db: orm对象
        :param action: continue / polish / translate
        :param ctx: 条目上下文
        :param style: 润色风格
        :param keywords: 续写关键词
        :param locale: 界面语言
        :param instruction: 作者补充意见，仅 refine 用
        :return: (改写后的正文, 出结果的模型标识)
        :raises ServiceException: 池子是空的，或池里所有模型都失败了
        """
        messages = build_messages(action, ctx, style=style, keywords=keywords, locale=locale, instruction=instruction)

        return await cls.complete(query_db, messages, failure_hint='AI 改写失败')
