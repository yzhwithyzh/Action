import hashlib
import hmac
from base64 import b64encode
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import PurePosixPath
from uuid import uuid4

import httpx
from starlette.status import HTTP_200_OK

from config.env import OssConfig
from exceptions.exception import ServiceException
from utils.log_util import logger

# 官网图片允许的扩展名。刻意不复用 UploadConfig.DEFAULT_ALLOWED_EXTENSION：
# 那份清单含 doc/zip/mp4，而这条通道只服务「会被 <img> 直接引用的公开图片」，
# 放宽到文档/压缩包等于开了一个任意文件公网托管入口。
ALLOWED_IMAGE_EXTENSIONS = frozenset({'jpg', 'jpeg', 'png', 'webp', 'gif'})
# 扩展名 → Content-Type。OSS 不会自己推断，传错了浏览器会当附件下载而不是显示。
_CONTENT_TYPES = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'webp': 'image/webp',
    'gif': 'image/gif',
}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


class OssUtil:
    """
    阿里云 OSS 工具类

    只用到 PutObject 一个接口，因此手写 V1 签名 + httpx，不引入 oss2
    （它会连带拖进 aliyun-python-sdk-core、crcmod 等一串依赖）。
    与 module_action/service/mail_service.py 对 DirectMail 的做法一致。
    """

    @classmethod
    def is_configured(cls) -> bool:
        """
        判断 OSS 是否可用

        :return: 配置齐全且启用时为 True
        """
        return bool(OssConfig.oss_enabled and OssConfig.oss_access_key_id and OssConfig.oss_access_key_secret)

    @classmethod
    def normalize_extension(cls, filename: str) -> str:
        """
        取出并校验文件扩展名

        :param filename: 原始文件名
        :return: 小写扩展名（不含点）
        """
        suffix = PurePosixPath(filename or '').suffix.lstrip('.').lower()
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            raise ServiceException(message=f'不支持的图片格式，仅支持 {"/".join(sorted(ALLOWED_IMAGE_EXTENSIONS))}')

        return suffix

    @classmethod
    def build_object_key(cls, category: str, extension: str) -> str:
        """
        生成对象键

        用随机名而不是原文件名：原名可能含中文/空格/路径分隔符，且同名覆盖会让
        已经引用旧图的页面悄悄换图。

        :param category: 业务目录，如 team
        :param extension: 扩展名
        :return: 对象键，如 site/team/3f2a….jpg
        """
        prefix = OssConfig.oss_dir_prefix.strip('/')
        parts = [p for p in (prefix, category.strip('/')) if p]

        return '/'.join([*parts, f'{uuid4().hex}.{extension}'])

    @classmethod
    def public_url(cls, object_key: str) -> str:
        """
        拼对象的公网访问地址

        :param object_key: 对象键
        :return: 公网 URL
        """
        return f'{OssConfig.public_base_url}/{object_key.lstrip("/")}'

    @classmethod
    def _signature(cls, verb: str, object_key: str, content_type: str, date: str) -> str:
        """
        计算 OSS V1 签名

        规范串的字段顺序、`\\n` 的个数、CanonicalizedOSSHeaders 的排序都不能改，
        任一处不一致都会得到 SignatureDoesNotMatch。
        oss_object_acl 留空时**整行都不能出现**，不是留一个空值。

        :param verb: HTTP 方法
        :param object_key: 对象键
        :param content_type: 内容类型
        :param date: GMT 格式时间
        :return: 签名串
        """
        acl = OssConfig.oss_object_acl
        canonicalized_headers = f'x-oss-object-acl:{acl}\n' if acl else ''
        canonicalized_resource = f'/{OssConfig.oss_bucket}/{object_key}'
        string_to_sign = f'{verb}\n\n{content_type}\n{date}\n{canonicalized_headers}{canonicalized_resource}'
        digest = hmac.new(
            OssConfig.oss_access_key_secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1
        ).digest()

        return b64encode(digest).decode('utf-8')

    @classmethod
    async def put_object(cls, object_key: str, content: bytes, extension: str) -> str:
        """
        上传对象并返回公网地址

        :param object_key: 对象键
        :param content: 文件字节
        :param extension: 扩展名，用于推 Content-Type
        :return: 公网 URL
        """
        if not cls.is_configured():
            raise ServiceException(message='对象存储未配置，请联系管理员在 .env 中配置 OSS_* 后重试')

        content_type = _CONTENT_TYPES[extension]
        date = format_datetime(datetime.now(timezone.utc), usegmt=True)
        url = f'https://{OssConfig.oss_bucket}.{OssConfig.oss_endpoint}/{object_key}'
        headers = {
            'Date': date,
            'Content-Type': content_type,
            'Authorization': f'OSS {OssConfig.oss_access_key_id}:'
            f'{cls._signature("PUT", object_key, content_type, date)}',
        }
        if OssConfig.oss_object_acl:
            headers['x-oss-object-acl'] = OssConfig.oss_object_acl

        async with httpx.AsyncClient(timeout=OssConfig.oss_timeout_seconds) as client:
            response = await client.put(url, content=content, headers=headers)

        if response.status_code != HTTP_200_OK:
            # OSS 的错误体是 XML，直接透传给前端没意义，落日志便于排查签名/权限问题
            logger.error(f'OSS 上传失败 {response.status_code}: {response.text[:500]}')
            # 这一条单独提示：桶开了「阻止公共访问」时逐对象授公共读会被拒，
            # 报文只说 AccessDenied，照着改桶 ACL 会走弯路。
            if 'Put public object acl is not allowed' in response.text:
                raise ServiceException(
                    message='上传失败：桶开启了「阻止公共访问」，请改为桶级公共读，或把 OSS_OBJECT_ACL 置空'
                )
            raise ServiceException(message=f'图片上传失败（OSS {response.status_code}）')

        return cls.public_url(object_key)

    @classmethod
    async def is_publicly_readable(cls, url: str) -> bool:
        """
        匿名 GET 探一次，确认对象真的能被公网读到

        官网是预渲染的静态站，`<img src>` 由匿名访客直接请求 OSS。
        「传上去了」和「读得到」是两件事：桶是私有且没授公共读时，
        上传会成功、页面却全是 403 —— 这个探测就是为了不把那种状态当成成功。

        :param url: 对象公网地址
        :return: 匿名可读为 True
        """
        async with httpx.AsyncClient(timeout=OssConfig.oss_timeout_seconds) as client:
            response = await client.get(url)

        return response.status_code == HTTP_200_OK

    @classmethod
    async def delete_object(cls, object_key: str) -> None:
        """
        删除对象（供联调自检后清理用）

        :param object_key: 对象键
        :return: None
        """
        date = format_datetime(datetime.now(timezone.utc), usegmt=True)
        url = f'https://{OssConfig.oss_bucket}.{OssConfig.oss_endpoint}/{object_key}'
        headers = {
            'Date': date,
            'Authorization': f'OSS {OssConfig.oss_access_key_id}:{cls._signature("DELETE", object_key, "", date)}',
        }

        async with httpx.AsyncClient(timeout=OssConfig.oss_timeout_seconds) as client:
            await client.delete(url, headers=headers)
