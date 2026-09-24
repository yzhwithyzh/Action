"""关闭思考模式：各厂商的请求参数不同名，按端点与模型名挑对的那一个。

后台「AI模型管理」的「支持推理」配成否时，调用方要真的让模型别思考 —— 思维链按输出价计费，
实测火山方舟 deepseek 开着思考时一批 8 条的判定输出 2k–8k token，关掉后约 600，结论基本不变。
但「关」这件事各家写法不一样，发错了要么被静默忽略（照样思考、照样计费），要么直接 400：

    火山方舟 / DeepSeek / 智谱 GLM   {"thinking": {"type": "disabled"}}
    阿里百炼（qwen，含 *.maas 工作空间端点）、qwen 系第三方托管
                                     {"enable_thinking": false}
    OpenAI 官方                       不认上面任何一个，会报 unrecognized argument → 不下发

**按端点判，不按 `provider` 判**：库里 provider 与实际端点常对不上（dev 库那条 deepseek 的
provider 是 `DeepSeek`，base_url 却是火山方舟），而参数认不认是端点说了算。端点判不出来时
再看模型名（qwen 放在 SiliconFlow 之类的托管平台上，认的仍是 `enable_thinking`）。

纯函数、只依赖标准库：后端 `ai_assist_service`（手拼请求体）与 worker 的
`tools/common/model_registry`（经 LangChain 的 `extra_body`）共用这一份，两边别各写一套。
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

#: 没配 base_url 时，按 provider 推一个默认端点（与 srd-engine 的 `_OPENAI_COMPATIBLE_DEFAULT_BASE` 同源）
_DEFAULT_HOST = {
    'OpenAI': 'api.openai.com',
    'DeepSeek': 'api.deepseek.com',
    'DashScope': 'dashscope.aliyuncs.com',
    'ZhipuAI': 'open.bigmodel.cn',
}

THINKING_DISABLED: dict[str, Any] = {'thinking': {'type': 'disabled'}}
ENABLE_THINKING_FALSE: dict[str, Any] = {'enable_thinking': False}


def _host(provider: str, base_url: str | None) -> str:
    if base_url and base_url.strip():
        return (urlparse(base_url.strip()).hostname or '').lower()

    return _DEFAULT_HOST.get(provider, '')


def thinking_off_params(provider: str | None, base_url: str | None, model_code: str | None) -> dict[str, Any]:
    """关闭思考要往请求体里并入的字段；不该下发时返回空字典。

    :param provider: `ai_models.provider`
    :param base_url: `ai_models.base_url`（可空）
    :param model_code: `ai_models.model_code`
    :return: 形如 `{'thinking': {'type': 'disabled'}}` 或 `{'enable_thinking': False}`，或 `{}`
    """
    provider = (provider or '').strip()
    model = (model_code or '').strip().lower()
    # 非 OpenAI 兼容协议：Anthropic / Gemini 的思考本来就要显式打开，而且请求体结构不同
    if provider in ('Anthropic', 'Google'):
        return {}

    host = _host(provider, base_url)
    if host == 'api.openai.com':
        return {}
    if host.endswith('aliyuncs.com'):
        return dict(ENABLE_THINKING_FALSE)
    if host.endswith(('volces.com', 'bigmodel.cn', 'deepseek.com')):
        return {'thinking': dict(THINKING_DISABLED['thinking'])}
    # 端点不认识（自建网关、第三方托管）：按模型家族猜
    if model.startswith(('qwen', 'qwq')):
        return dict(ENABLE_THINKING_FALSE)

    return {'thinking': dict(THINKING_DISABLED['thinking'])}
