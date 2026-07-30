import hashlib
import hmac
from base64 import b64encode
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

import httpx
from starlette.status import HTTP_200_OK

from config.env import AppConfig, MailConfig
from utils.log_util import logger

# MAIL_ENABLED=false 的「不发信、把验证码写日志」降级只在这个运行环境下成立。
# 其余环境（尤其是生产）漏配 MAIL_ENABLED 时必须显式失败，否则接口会一路报
# 「验证码已发送」而用户永远收不到信，属于静默失效。
DEV_APP_ENV = 'dev'
# 验证码邮件正文模板：双语平权，按用户提交时的界面语言取对应一版。
# 有效期不写死在正文里，由调用方把 EMAIL_CODE_EXPIRE_MINUTES 插进来——常量改了
# 而正文不变的话，用户与客服拿到的是错误信息。
_MAIL_TEMPLATES: dict[str, dict[str, str]] = {
    'zh': {
        'subject': 'ACTION 平台验证码',
        'body': (
            "<div style=\"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
            'font-size:14px;line-height:1.8;color:#1f2933">'
            '<p>您好，</p>'
            '<p>您正在使用邮箱验证码进行 ACTION 针刺临床研究智能平台的身份验证，验证码为：</p>'
            '<p style="font-size:28px;letter-spacing:6px;font-weight:600;color:#0f4c5c">{code}</p>'
            '<p>验证码 {minutes} 分钟内有效，请勿转发给他人。若非本人操作，请忽略本邮件。</p>'
            '<p style="color:#7b8794">ACTION（ACupuncTure Intelligent helper ON clinical research）</p>'
            '</div>'
        ),
    },
    'en': {
        'subject': 'ACTION Platform Verification Code',
        'body': (
            "<div style=\"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
            'font-size:14px;line-height:1.8;color:#1f2933">'
            '<p>Hello,</p>'
            '<p>You are verifying your identity on ACTION, the intelligent platform for acupuncture '
            'clinical research. Your verification code is:</p>'
            '<p style="font-size:28px;letter-spacing:6px;font-weight:600;color:#0f4c5c">{code}</p>'
            '<p>The code expires in {minutes} minutes. Please do not share it. '
            'If this was not you, ignore this email.</p>'
            '<p style="color:#7b8794">ACTION (ACupuncTure Intelligent helper ON clinical research)</p>'
            '</div>'
        ),
    },
}


class MailService:
    """
    邮件发送服务层

    目前只承担访客验证码邮件，走阿里云 DirectMail 的 SingleSendMail RPC 接口。
    没有引入 alibabacloud_* SDK：只用到一个接口，手写 HMAC-SHA1 签名 + httpx
    比多拉一整套 SDK 依赖更轻。
    """

    # DirectMail 的接入点并非「每个地域一个子域」：中国站所有 cn-* 地域共用
    # dm.aliyuncs.com，只有国际站才按地域拆（ap-southeast-1 新加坡、ap-southeast-2 悉尼）。
    # 按 RegionId 一律拼子域会得到 dm.cn-hangzhou.aliyuncs.com 这种不存在的域名，
    # 请求在 DNS 阶段就死于 getaddrinfo failed，看起来像断网，实则是配置错。
    # RegionId 参数仍按 MAIL_REGION 原样上送，签名与计费地域不受接入点收敛影响。
    _CN_ENDPOINT = 'https://dm.aliyuncs.com/'
    _INTL_ENDPOINT_TEMPLATE = 'https://dm.{region}.aliyuncs.com/'
    _CN_REGION_PREFIX = 'cn-'
    _API_VERSION = '2015-11-23'
    _REQUEST_TIMEOUT_SECONDS = 10.0

    @classmethod
    async def send_verify_code(
        cls, email: str, code: str, lang: Literal['zh', 'en'] = 'zh', *, expire_minutes: int
    ) -> bool:
        """
        发送邮箱验证码邮件

        发信失败不会抛出异常，也不会把底层错误透给调用方：网络/凭据细节回传给匿名接口
        既无意义又会泄露服务端信息。但**返回值必须被调用方检查**——返回 False 时调用方
        要撤掉刚写入的验证码与冷却键，否则凭据过期/额度耗尽时用户永远收不到信却被
        告知「验证码已发送」。

        返回 True 有两种情形：真的外发成功，以及**开发环境**下 MAIL_ENABLED=false 的
        联调态（验证码已写进日志，对联调而言就是「已投递」）。只有「已启用但没送出去」
        与「非开发环境却没开启邮件」才返回 False。

        :param email: 收件邮箱
        :param code: 6位数字验证码
        :param lang: 邮件语言（zh中文 en英文）
        :param expire_minutes: 验证码有效期分钟数（写进正文，与业务侧常量同源）
        :return: 验证码是否已按当前配置成功投递
        """
        template = _MAIL_TEMPLATES.get(lang, _MAIL_TEMPLATES['zh'])
        subject = template['subject']
        body = template['body'].format(code=code, minutes=expire_minutes)
        if not MailConfig.mail_enabled:
            if AppConfig.app_env != DEV_APP_ENV:
                # 生产漏配 MAIL_ENABLED 时绝不能静默降级：那会让接口一路报「验证码已
                # 发送」，而验证码只躺在服务端日志里，故障要靠用户投诉才被发现。
                logger.error(f'当前环境{AppConfig.app_env}未启用邮件发送，邮箱{email}的验证码无法投递')
                return False
            # 开发联调态：不外发，把验证码打到日志里，接口行为与真实发信保持一致。
            logger.warning(f'邮件发送未启用，邮箱{email}的验证码为{code}（{lang}）')
            return True
        if not (MailConfig.mail_access_key_id and MailConfig.mail_access_key_secret and MailConfig.mail_account_name):
            logger.error('邮件发送已启用但DirectMail凭据不完整，请检查MAIL_*配置')
            return False
        try:
            params = cls._build_single_send_mail_params(email, subject, body)
            endpoint = cls._resolve_endpoint()
            async with httpx.AsyncClient(timeout=cls._REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(endpoint, data=params)
            if response.status_code != HTTP_200_OK:
                logger.error(f'邮箱{email}验证码邮件发送失败，DirectMail返回状态码{response.status_code}')
                return False
        except Exception as e:
            logger.error(f'邮箱{email}验证码邮件发送异常：{e}')
            return False
        logger.info(f'邮箱{email}验证码邮件发送成功')

        return True

    @classmethod
    def _resolve_endpoint(cls) -> str:
        """
        按地域解析DirectMail接入点

        地域缺省时按中国站处理：MAIL_REGION 漏配不该演变成一个拼不出域名的请求。

        :return: SingleSendMail请求的完整endpoint
        """
        region = MailConfig.mail_region or ''
        if not region or region.startswith(cls._CN_REGION_PREFIX):
            return cls._CN_ENDPOINT

        return cls._INTL_ENDPOINT_TEMPLATE.format(region=region)

    @classmethod
    def _build_single_send_mail_params(cls, email: str, subject: str, body: str) -> dict[str, str]:
        """
        构建DirectMail SingleSendMail请求参数（含签名）

        :param email: 收件邮箱
        :param subject: 邮件主题
        :param body: 邮件HTML正文
        :return: 已签名的请求参数字典
        """
        params = {
            'Action': 'SingleSendMail',
            'AccountName': MailConfig.mail_account_name,
            'AddressType': '1',
            'ReplyToAddress': 'false',
            'ToAddress': email,
            'FromAlias': MailConfig.mail_from_alias,
            'Subject': subject,
            'HtmlBody': body,
            'Format': 'JSON',
            'Version': cls._API_VERSION,
            'RegionId': MailConfig.mail_region,
            'AccessKeyId': MailConfig.mail_access_key_id,
            'SignatureMethod': 'HMAC-SHA1',
            'SignatureVersion': '1.0',
            'SignatureNonce': uuid4().hex,
            'Timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        }
        params['Signature'] = cls._sign(params, MailConfig.mail_access_key_secret)

        return params

    @classmethod
    def _sign(cls, params: dict[str, str], access_key_secret: str) -> str:
        """
        按阿里云RPC规范计算请求签名

        :param params: 未含Signature的请求参数字典
        :param access_key_secret: 阿里云AccessKey Secret
        :return: Base64编码的签名串
        """
        canonicalized = '&'.join(
            f'{cls._percent_encode(k)}={cls._percent_encode(v)}' for k, v in sorted(params.items())
        )
        string_to_sign = f'POST&{cls._percent_encode("/")}&{cls._percent_encode(canonicalized)}'
        digest = hmac.new(f'{access_key_secret}&'.encode(), string_to_sign.encode('utf-8'), hashlib.sha1).digest()

        return b64encode(digest).decode('utf-8')

    @classmethod
    def _percent_encode(cls, value: str) -> str:
        """
        按RFC3986规则做百分号编码

        阿里云要求：空格编为 `%20`、`*` 编为 `%2A`、`~` 不编码、`/` 也要编码。
        Python 3.7+ 的 `quote` 恰好把 `_.-~` 视为永远安全字符，因此只要显式传
        safe=''（覆盖默认的 safe='/'）即可完全对齐，否则签名串与服务端计算结果
        不一致，会直接报 SignatureDoesNotMatch。

        :param value: 待编码的原始值
        :return: 编码后的字符串
        """
        return quote(value, safe='')
