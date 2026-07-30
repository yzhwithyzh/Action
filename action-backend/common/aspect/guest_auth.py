from datetime import timedelta

import jwt
from fastapi import Depends, Request, params
from jwt.exceptions import InvalidTokenError
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from common.enums import RedisInitKeyConfig
from config.env import JwtConfig
from config.get_db import get_db
from exceptions.exception import AuthException
from module_action.dao.action_dao import GUEST_USER_TYPE, GuestProfileDao
from module_action.entity.vo.action_vo import GuestInfoModel
from module_action.service.guest_auth_service import is_guest_account_disabled
from utils.log_util import logger

# 与后台 get_current_user 保持一致的对外文案，避免通过报错差异区分两套账号体系
TOKEN_INVALID_MESSAGE = '用户token不合法'
TOKEN_EXPIRED_MESSAGE = '用户token已失效，请重新登录'
TOKEN_MISSING_MESSAGE = '用户未登录，请先完成登录'
# Redis 不可用时返回给调用方的中文提示：绝不能把 redis-py 原始错误串（含 host:port）
# 交给兜底 handler 的 str(exc) 回给公开接口
REDIS_UNAVAILABLE_MESSAGE = '服务暂时不可用，请稍后重试'
BEARER_PREFIX = 'bearer'
# 合法的 Authorization 头恰好由「scheme + 令牌」两段组成
BEARER_HEADER_PART_COUNT = 2
# 捕获 redis-py 的异常基类，而不只是 ConnectionError/TimeoutError：
# OutOfMemoryError、ReadOnlyError、NoPermissionError、ClusterDownError 都继承自
# ResponseError(RedisError)，与 ConnectionError 之间没有任何继承关系。只捕连接类
# 异常时，「OOM command not allowed when used memory > 'maxmemory'」这类服务端
# 错误串会穿透到兜底 handler，被原样回给匿名调用方。
REDIS_UNAVAILABLE_ERRORS = (RedisError,)


def extract_bearer_token(authorization: str | None) -> str | None:
    """
    从Authorization请求头中健壮地取出Bearer令牌

    三种坏输入必须都能安全处理，否则会变成未捕获的 500 或误判：
    - `Bearer`（只有前缀没有值）：`split(' ')[1]` 会 IndexError
    - `BearerXYZ`（前缀后无空格）：不是合法的 Bearer 头，不能把 XYZ 当令牌
    - `bearer <token>`（小写前缀）：RFC 6750 规定 scheme 大小写不敏感，
      用 startswith('Bearer') 判断会把合法令牌当成失效令牌

    :param authorization: Authorization请求头原始值
    :return: 令牌字符串，取不到时返回None
    """
    if not authorization:
        return None
    parts = authorization.strip().split(None, 1)
    if len(parts) != BEARER_HEADER_PART_COUNT or parts[0].lower() != BEARER_PREFIX:
        return None

    return parts[1].strip() or None


class GuestUser:
    """
    官网访客身份校验依赖类

    访客刻意不复用 `LoginService.get_current_user`：那套会顺带组装角色、菜单、岗位、
    密码过期提醒等后台专属信息，对访客既无意义又白白多打好几条 SQL。
    这里做两道闸门——payload 里的 user_type 决定这张 token 能进哪扇门，库里的
    user_type 决定这个账号能走哪条路，两者都必须是 '01'。
    """

    async def __call__(self, request: Request, query_db: AsyncSession = Depends(get_db)) -> GuestInfoModel:
        """
        执行访客身份校验

        :param request: 当前请求对象
        :param query_db: 数据库会话
        :return: 当前访客信息
        :raise: 令牌异常AuthException
        """
        token = extract_bearer_token(request.headers.get('Authorization'))
        if not token:
            raise AuthException(data='', message=TOKEN_MISSING_MESSAGE)
        try:
            payload = jwt.decode(token, JwtConfig.jwt_secret_key, algorithms=[JwtConfig.jwt_algorithm])
            session_id: str | None = payload.get('session_id')
            if not session_id or payload.get('user_type') != GUEST_USER_TYPE:
                logger.warning(TOKEN_INVALID_MESSAGE)
                raise AuthException(data='', message=TOKEN_INVALID_MESSAGE)
            # int() 必须留在 try 内：payload 被篡改成非数字 user_id 时，
            # 裸的 ValueError 会一路冒到兜底 handler 变成 500
            user_id = int(payload.get('user_id'))
        except (InvalidTokenError, TypeError, ValueError) as e:
            logger.warning(TOKEN_EXPIRED_MESSAGE)
            raise AuthException(data='', message=TOKEN_EXPIRED_MESSAGE) from e
        await self._check_and_renew_redis_token(request, session_id, token)
        guest_row = await GuestProfileDao.get_guest_by_user_id(query_db, user_id)
        # 账号可用性判定与 GuestAuthService.login 收敛到同一个函数：两处判定一旦分叉
        # （一个写 status == '1' 拒绝、一个写 status != '0' 拒绝），status 为 NULL 的
        # 账号就会「登录成功拿到 token，下一个请求就 401」，用户陷入死循环。
        if guest_row is None or is_guest_account_disabled(guest_row[0]):
            logger.warning(TOKEN_INVALID_MESSAGE)
            raise AuthException(data='', message=TOKEN_INVALID_MESSAGE)

        return GuestInfoModel(
            userId=guest_row[0].user_id,
            email=guest_row[0].email or '',
            username=guest_row[0].nick_name or '',
            institution=guest_row[1].institution if guest_row[1] else None,
            position=guest_row[1].position if guest_row[1] else None,
        )

    async def _check_and_renew_redis_token(self, request: Request, session_id: str, token: str) -> None:
        """
        比对Redis中的会话令牌并续期

        :param request: 当前请求对象
        :param session_id: 会话编号
        :param token: 请求携带的令牌
        :return: None
        :raise: 令牌异常AuthException
        """
        token_key = f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}'
        try:
            redis_token = await request.app.state.redis.get(token_key)
            if not redis_token or token != redis_token:
                logger.warning(TOKEN_EXPIRED_MESSAGE)
                raise AuthException(data='', message=TOKEN_EXPIRED_MESSAGE)
            await request.app.state.redis.set(
                token_key, redis_token, ex=timedelta(minutes=JwtConfig.jwt_redis_expire_minutes)
            )
        except REDIS_UNAVAILABLE_ERRORS as e:
            logger.error(f'Redis不可用，校验访客会话{session_id}失败：{e}')
            raise AuthException(data='', message=REDIS_UNAVAILABLE_MESSAGE) from e


def GuestUserDependency() -> params.Depends:  # noqa: N802
    """
    当前登录访客信息依赖

    :return: 当前登录访客信息依赖
    """
    return Depends(GuestUser())
