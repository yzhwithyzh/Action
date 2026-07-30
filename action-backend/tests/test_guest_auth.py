import asyncio
import os
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request
from pydantic_validation_decorator import FieldValidationError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import OutOfMemoryError as RedisOutOfMemoryError
from redis.exceptions import ResponseError as RedisResponseError
from sqlalchemy import Column, Integer, String, true
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from common.aspect.guest_auth import GuestUser, extract_bearer_token
from common.constant import CommonConstant
from common.enums import RedisInitKeyConfig
from config.database import create_async_session_local
from exceptions.exception import AuthException, LoginException, ModelValidatorException, ServiceException
from module_action.dao.action_dao import GuestProfileDao
from module_action.entity.vo.action_vo import GuestEmailCodeModel, GuestLoginModel, GuestRegisterModel
from module_action.service.guest_auth_service import (
    EMAIL_CODE_EXPIRE_MINUTES,
    LOGIN_IP_MAX_LENGTH,
    GuestAuthService,
)
from module_action.service.mail_service import _MAIL_TEMPLATES as MAIL_TEMPLATES
from module_action.service.mail_service import MailService
from module_admin.dao.user_dao import UserDao
from module_admin.entity.do.user_do import SysUser
from module_admin.entity.vo.login_vo import UserLogin
from module_admin.entity.vo.user_vo import UserPageQueryModel, UserRolePageQueryModel
from module_admin.service.login_service import LoginService
from utils.pwd_util import PwdUtil

GUEST_SERVICE_MODULE = 'module_action.service.guest_auth_service'
GUEST_ASPECT_MODULE = 'common.aspect.guest_auth'
LOGIN_SERVICE_MODULE = 'module_admin.service.login_service'
TEST_EMAIL = 'guest@example.com'
TEST_CODE = '123456'
EMAIL_CODE_LENGTH = 6
# 25 个中文字符 = 75 字节：max_length=50（字符数）放行，但超过 bcrypt 的 72 字节上限
OVERSIZE_PASSWORD = '密' * 25


class FakeRedis:
    """
    进程内假Redis，只实现本模块用到的 get / set / delete / incr / expire。

    每个方法先 `await asyncio.sleep(0)` 让出事件循环，这样 asyncio.gather 里的
    两个协程能真正交错执行，否则「并发同邮箱注册」根本测不出竞态。让出之后的
    读改写整体不再 await，正是真实 Redis 单命令的原子性语义。

    `set` 支持 nx 语义：60 秒冷却键靠 SET NX 的返回值判定是否命中频控，
    假实现不支持 nx 的话这条防线在测试里就是空跑。
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        await asyncio.sleep(0)
        return self.store.get(key)

    async def set(self, key: str, value: Any, ex: Any = None, nx: bool = False) -> bool | None:
        await asyncio.sleep(0)
        if nx and key in self.store:
            return None
        self.store[key] = str(value)
        return True

    async def incr(self, key: str, amount: int = 1) -> int:
        await asyncio.sleep(0)
        cached = self.store.get(key, '0')
        if not cached.lstrip('-').isdigit():
            # 真实 Redis 对非整数值的 INCR 回的是 ResponseError，不是 Python 的 ValueError
            raise RedisResponseError('value is not an integer or out of range')
        value = int(cached) + amount
        self.store[key] = str(value)
        return value

    async def expire(self, key: str, ex: Any = None) -> bool:
        await asyncio.sleep(0)
        return key in self.store

    async def delete(self, *keys: str) -> int:
        await asyncio.sleep(0)
        deleted = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                deleted += 1
        return deleted


class ExpiringRedis(FakeRedis):
    """
    模拟「GET 与 DEL 之间验证码自然过期」的假Redis：读得到，删返回 0
    """

    async def delete(self, *keys: str) -> int:
        await asyncio.sleep(0)
        for key in keys:
            self.store.pop(key, None)
        return 0


class BrokenRedis(FakeRedis):
    """
    模拟Redis不可用：所有命令抛 redis-py 的 ConnectionError
    """

    async def get(self, key: str) -> str | None:
        raise RedisConnectionError('Error connecting to 10.1.2.3:6379. Connection refused.')

    async def set(self, key: str, value: Any, ex: Any = None, nx: bool = False) -> bool | None:
        raise RedisConnectionError('Error connecting to 10.1.2.3:6379. Connection refused.')

    async def incr(self, key: str, amount: int = 1) -> int:
        raise RedisConnectionError('Error connecting to 10.1.2.3:6379. Connection refused.')

    async def expire(self, key: str, ex: Any = None) -> bool:
        raise RedisConnectionError('Error connecting to 10.1.2.3:6379. Connection refused.')

    async def delete(self, *keys: str) -> int:
        raise RedisConnectionError('Error connecting to 10.1.2.3:6379. Connection refused.')


class OomRedis(FakeRedis):
    """
    模拟Redis写入被服务端拒绝：OutOfMemoryError 继承自 ResponseError(RedisError)，
    与 ConnectionError 之间没有任何继承关系
    """

    async def set(self, key: str, value: Any, ex: Any = None, nx: bool = False) -> bool | None:
        raise RedisOutOfMemoryError("OOM command not allowed when used memory > 'maxmemory'.")


class FakeSession:
    """
    假数据库会话，只记录 commit / rollback 次数
    """

    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


class CapturingSession(FakeSession):
    """
    只截获并记录 execute 收到的语句，用于对 DAO 编译出的 SQL 做断言
    """

    def __init__(self) -> None:
        super().__init__()
        self.statements: list[Any] = []

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        self.statements.append(statement)
        empty = SimpleNamespace(first=lambda: None)
        return SimpleNamespace(first=lambda: None, scalars=lambda: empty)


class ExpiredAttributeError(RuntimeError):
    """
    替身对象在「已过期」状态下被读属性时抛出，对应真实环境里的 MissingGreenlet
    """


class ExpiringOrmStub:
    """
    带 ORM 过期语义的实例替身

    真实的 `async_sessionmaker`（config/database.py:91）没传 expire_on_commit，取默认
    True：commit() 会 expire_all() 掉 identity map 里全部实例，rollback() 对非嵌套事务
    同样过期全部实例，此后任何属性读取都会在 async 上下文里抛 MissingGreenlet。
    原来的用例用 SimpleNamespace 当用户对象，完全没有这层语义，所以 46 条用例全绿
    也没能抓住「commit 之后读 user.user_id」这个 100% 必现的缺陷。
    """

    def __init__(self, **fields: Any) -> None:
        object.__setattr__(self, '_fields', dict(fields))
        object.__setattr__(self, '_expired', False)

    def expire(self) -> None:
        """
        标记实例已过期（模拟 SQLAlchemy 的 expire_all）

        :return: None
        """
        object.__setattr__(self, '_expired', True)

    def __getattr__(self, name: str) -> Any:
        fields = object.__getattribute__(self, '_fields')
        if name not in fields:
            raise AttributeError(name)
        if object.__getattribute__(self, '_expired'):
            raise ExpiredAttributeError(f'greenlet_spawn has not been called; can not refresh expired attribute {name}')
        return fields[name]


class ExpiringSession(FakeSession):
    """
    带 ORM 过期语义的假会话：commit()/rollback() 之后，登记进来的替身再读属性就抛
    """

    def __init__(self, *tracked: ExpiringOrmStub) -> None:
        super().__init__()
        self.tracked: list[ExpiringOrmStub] = list(tracked)

    async def commit(self) -> None:
        await super().commit()
        self._expire_all()

    async def rollback(self) -> None:
        await super().rollback()
        self._expire_all()

    def _expire_all(self) -> None:
        """
        过期掉所有登记的替身

        :return: None
        """
        for item in self.tracked:
            item.expire()


def build_request(
    redis: FakeRedis,
    headers: list[tuple[bytes, bytes]] | None = None,
    client: tuple[str, int] = ('10.0.0.9', 51234),
) -> Request:
    """
    构造带假Redis的请求对象

    :param redis: 假Redis实例
    :param headers: 请求头列表
    :param client: 直连来源地址
    :return: 请求对象
    """
    app = SimpleNamespace(state=SimpleNamespace(redis=redis))
    return Request(
        {
            'type': 'http',
            'method': 'POST',
            'path': '/action/site/auth/login',
            'headers': headers or [],
            'query_string': b'',
            'client': client,
            'app': app,
        }
    )


def build_guest_user(**overrides: Any) -> SimpleNamespace:
    """
    构造访客用户对象

    :param overrides: 需要覆盖的字段
    :return: 访客用户对象
    """
    user = {
        'user_id': 88,
        'user_name': 'guest_0123456789ab',
        'nick_name': '张三',
        'user_type': '01',
        'email': TEST_EMAIL,
        'password': PwdUtil.get_password_hash('Guest@123'),
        'status': '0',
        'del_flag': '0',
    }
    user.update(overrides)
    return SimpleNamespace(**user)


def code_key(scene: str, email: str = TEST_EMAIL) -> str:
    """
    构造验证码Redis键

    :param scene: 验证码场景
    :param email: 邮箱
    :return: Redis键
    """
    return f'{RedisInitKeyConfig.EMAIL_CODE.key}:{scene}:{email.lower()}'


def cd_key(scene: str, email: str = TEST_EMAIL) -> str:
    """
    构造验证码冷却Redis键

    :param scene: 验证码场景
    :param email: 邮箱
    :return: Redis键
    """
    return f'{RedisInitKeyConfig.EMAIL_CODE_CD.key}:{scene}:{email.lower()}'


def fail_key(scene: str, email: str = TEST_EMAIL) -> str:
    """
    构造凭据失败计数Redis键

    :param scene: 场景
    :param email: 邮箱
    :return: Redis键
    """
    return f'{RedisInitKeyConfig.GUEST_LOGIN_FAIL.key}:{scene}:{email.lower()}'


def lock_key(scene: str, email: str = TEST_EMAIL) -> str:
    """
    构造凭据失败锁定Redis键

    :param scene: 场景
    :param email: 邮箱
    :return: Redis键
    """
    return f'{RedisInitKeyConfig.GUEST_LOGIN_LOCK.key}:{scene}:{email.lower()}'


def build_profile(institution: str | None = '广州中医药大学', position: str | None = '研究员') -> SimpleNamespace:
    """
    构造访客档案对象

    :param institution: 所属机构
    :param position: 职位
    :return: 访客档案对象
    """
    return SimpleNamespace(institution=institution, position=position)


# ---------------------------------------------------------------- 发送验证码


def test_email_code_rejects_when_still_in_cooldown() -> None:
    redis = FakeRedis()
    redis.store[cd_key('register')] = '1'
    request = build_request(redis)

    with pytest.raises(ServiceException) as error:
        asyncio.run(
            GuestAuthService.send_email_code(
                request, FakeSession(), GuestEmailCodeModel(email=TEST_EMAIL, scene='register')
            )
        )

    assert error.value.message == '发送过于频繁，请稍后再试'
    assert code_key('register') not in redis.store


def test_email_code_rejects_registered_email_in_register_scene() -> None:
    redis = FakeRedis()
    request = build_request(redis)

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email',
            new=AsyncMock(return_value=build_guest_user()),
        ),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(
            GuestAuthService.send_email_code(
                request, FakeSession(), GuestEmailCodeModel(email=TEST_EMAIL, scene='register')
            )
        )

    assert error.value.message == '该邮箱已注册'
    assert code_key('register') not in redis.store
    # 冷却键必须已经落地，否则「第二次是否被频控」会变成邮箱是否已注册的探测器
    assert cd_key('register') in redis.store


def test_email_code_is_silent_for_unknown_email_in_login_scene() -> None:
    redis = FakeRedis()
    request = build_request(redis)

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.MailService.send_verify_code', new=AsyncMock()) as send_mail,
    ):
        result = asyncio.run(
            GuestAuthService.send_email_code(
                request, FakeSession(), GuestEmailCodeModel(email=TEST_EMAIL, scene='login')
            )
        )

    assert result == '验证码已发送'
    assert code_key('login') not in redis.store
    send_mail.assert_not_awaited()


def test_email_code_writes_redis_and_sends_mail_for_known_email() -> None:
    redis = FakeRedis()
    request = build_request(redis)

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        patch(f'{GUEST_SERVICE_MODULE}.MailService.send_verify_code', new=AsyncMock()) as send_mail,
    ):
        asyncio.run(
            GuestAuthService.send_email_code(
                request, FakeSession(), GuestEmailCodeModel(email=TEST_EMAIL, scene='login', sourceLang='en')
            )
        )

    assert redis.store[code_key('login')].isdigit()
    assert len(redis.store[code_key('login')]) == EMAIL_CODE_LENGTH
    send_mail.assert_awaited_once()
    assert send_mail.await_args.args[2] == 'en'


# ---------------------------------------------------------------- 注册


def build_register_model(**overrides: Any) -> GuestRegisterModel:
    """
    构造注册入参

    :param overrides: 需要覆盖的字段
    :return: 注册入参
    """
    payload = {
        'email': TEST_EMAIL,
        'code': TEST_CODE,
        'username': '张三',
        'institution': '广州中医药大学',
        'position': '研究员',
        'password': 'Guest@123',
        'confirmPassword': 'Guest@123',
    }
    payload.update(overrides)
    return GuestRegisterModel(**payload)


def test_register_rejects_password_mismatch() -> None:
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)

    with pytest.raises(ServiceException) as error:
        asyncio.run(
            GuestAuthService.register(request, FakeSession(), build_register_model(confirmPassword='Other@123'))
        )

    assert error.value.message == '两次输入的密码不一致'
    # 密码都没对上，验证码不能被消费掉
    assert redis.store[code_key('register')] == TEST_CODE


def test_register_rejects_wrong_code() -> None:
    redis = FakeRedis()
    redis.store[code_key('register')] = '654321'
    request = build_request(redis)

    with pytest.raises(ServiceException) as error:
        asyncio.run(GuestAuthService.register(request, FakeSession(), build_register_model()))

    assert error.value.message == '验证码错误或已过期'


def test_register_rejects_expired_code() -> None:
    redis = FakeRedis()
    request = build_request(redis)

    with pytest.raises(ServiceException) as error:
        asyncio.run(GuestAuthService.register(request, FakeSession(), build_register_model()))

    assert error.value.message == '验证码错误或已过期'


def test_register_rejects_already_registered_email() -> None:
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email',
            new=AsyncMock(return_value=build_guest_user()),
        ),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(GuestAuthService.register(request, FakeSession(), build_register_model()))

    assert error.value.message == '该邮箱已注册'


def test_register_consumes_code_so_it_cannot_be_replayed() -> None:
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)
    session = FakeSession()

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserService.add_user_services', new=AsyncMock()),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.add_guest_profile_dao',
            new=AsyncMock(return_value=build_profile()),
        ),
    ):
        result = asyncio.run(GuestAuthService.register(request, session, build_register_model()))

        assert result.token
        assert result.guest.email == TEST_EMAIL
        assert result.guest.institution == '广州中医药大学'
        assert session.commit_count == 1
        # 校验通过后立刻删码，杜绝同一枚码被重放
        assert code_key('register') not in redis.store

        with pytest.raises(ServiceException) as error:
            asyncio.run(GuestAuthService.register(request, FakeSession(), build_register_model()))

    assert error.value.message == '验证码错误或已过期'


def test_register_writes_guest_token_into_redis() -> None:
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserService.add_user_services', new=AsyncMock()),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.add_guest_profile_dao',
            new=AsyncMock(return_value=build_profile()),
        ),
    ):
        result = asyncio.run(GuestAuthService.register(request, FakeSession(), build_register_model()))

    token_keys = [key for key in redis.store if key.startswith(f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:')]
    assert len(token_keys) == 1
    assert redis.store[token_keys[0]] == result.token


def test_register_rolls_back_user_when_profile_write_fails() -> None:
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)
    session = FakeSession()
    revoke = AsyncMock()

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserService.add_user_services', new=AsyncMock()),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.add_guest_profile_dao',
            new=AsyncMock(side_effect=RuntimeError('boom')),
        ),
        patch(f'{GUEST_SERVICE_MODULE}.UserDao.delete_user_dao', new=revoke),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(GuestAuthService.register(request, session, build_register_model()))

    assert error.value.message == '注册失败，请稍后重试'
    assert session.rollback_count == 1
    # 档案写失败必须把刚建的 sys_user 一并撤掉，不留「有账号没档案」的半成品
    revoke.assert_awaited_once()


def test_concurrent_register_with_same_email_lets_only_one_win() -> None:
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)

    async def run_both() -> list[Any]:
        return await asyncio.gather(
            GuestAuthService.register(request, FakeSession(), build_register_model()),
            GuestAuthService.register(request, FakeSession(), build_register_model()),
            return_exceptions=True,
        )

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserService.add_user_services', new=AsyncMock()),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.add_guest_profile_dao',
            new=AsyncMock(return_value=build_profile()),
        ) as add_profile,
    ):
        results = asyncio.run(run_both())

    succeeded = [item for item in results if not isinstance(item, Exception)]
    failed = [item for item in results if isinstance(item, ServiceException)]
    assert len(succeeded) == 1
    assert len(failed) == 1
    # DEL 返回 0 只说明「码已经不在了」，不能归因成「该邮箱已注册」——
    # 库里根本没有该账号时那句话会把正常用户彻底带偏
    assert failed[0].message == '验证码错误或已过期'
    # 只能有一条档案写入，不允许出现重复档案
    assert add_profile.await_count == 1


# ---------------------------------------------------------------- 登录


def test_login_with_unknown_email_and_admin_email_share_one_message() -> None:
    redis = FakeRedis()
    request = build_request(redis)

    # get_guest_by_email 已按 user_type='01' 过滤，管理员邮箱与不存在的邮箱在这里同样查不到
    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email', new=AsyncMock(return_value=None)),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(
            GuestAuthService.login(request, FakeSession(), GuestLoginModel(email=TEST_EMAIL, password='Guest@123'))
        )

    assert error.value.message == '邮箱或密码错误'


def test_login_with_wrong_password_uses_the_same_message() -> None:
    redis = FakeRedis()
    request = build_request(redis)

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(
            GuestAuthService.login(request, FakeSession(), GuestLoginModel(email=TEST_EMAIL, password='WrongPwd'))
        )

    assert error.value.message == '邮箱或密码错误'


def test_login_rejects_disabled_account() -> None:
    redis = FakeRedis()
    request = build_request(redis)

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(status='1'), None)),
        ),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(
            GuestAuthService.login(request, FakeSession(), GuestLoginModel(email=TEST_EMAIL, password='Guest@123'))
        )

    assert error.value.message == '账号已停用'


def test_login_with_email_code_consumes_the_code() -> None:
    redis = FakeRedis()
    redis.store[code_key('login')] = TEST_CODE
    request = build_request(redis)
    session = FakeSession()

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), SimpleNamespace(institution='机构', position='职位'))),
        ),
        patch(f'{GUEST_SERVICE_MODULE}.UserDao.edit_user_dao', new=AsyncMock()) as edit_user,
    ):
        result = asyncio.run(
            GuestAuthService.login(request, session, GuestLoginModel(email=TEST_EMAIL, code=TEST_CODE))
        )

    assert result.token
    assert result.guest.institution == '机构'
    assert code_key('login') not in redis.store
    assert session.commit_count == 1
    edit_user.assert_awaited_once()
    assert edit_user.await_args.args[1]['login_ip'] == '10.0.0.9'


def test_login_rejects_replayed_email_code() -> None:
    redis = FakeRedis()
    request = build_request(redis)

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(GuestAuthService.login(request, FakeSession(), GuestLoginModel(email=TEST_EMAIL, code=TEST_CODE)))

    # 登录路径下「验证码错误或已过期」是禁止出现的文案：它一出现，
    # 单次请求就能判定任意邮箱是否为本站访客
    assert error.value.message == '邮箱或密码错误'


def test_login_locks_email_after_repeated_failures() -> None:
    redis = FakeRedis()
    request = build_request(redis)

    with patch(
        f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
        new=AsyncMock(return_value=(build_guest_user(), None)),
    ):
        for _ in range(CommonConstant.PASSWORD_ERROR_COUNT + 1):
            with pytest.raises(ServiceException) as error:
                asyncio.run(
                    GuestAuthService.login(
                        request, FakeSession(), GuestLoginModel(email=TEST_EMAIL, password='WrongPwd')
                    )
                )
            assert error.value.message == '邮箱或密码错误'

        # 锁定后即使密码正确也拒绝，且文案与密码错误完全一致，不暴露「该邮箱被锁了」
        with pytest.raises(ServiceException) as locked:
            asyncio.run(
                GuestAuthService.login(request, FakeSession(), GuestLoginModel(email=TEST_EMAIL, password='Guest@123'))
            )

    assert locked.value.message == '邮箱或密码错误'
    assert lock_key('login') in redis.store
    # 注册与登录的计数/锁定互不串场，避免用错误注册码把别人的登录锁死
    assert lock_key('register') not in redis.store


def test_login_clears_failure_count_after_success() -> None:
    redis = FakeRedis()
    redis.store[fail_key('login')] = '3'
    request = build_request(redis)

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        patch(f'{GUEST_SERVICE_MODULE}.UserDao.edit_user_dao', new=AsyncMock()),
    ):
        asyncio.run(
            GuestAuthService.login(request, FakeSession(), GuestLoginModel(email=TEST_EMAIL, password='Guest@123'))
        )

    assert fail_key('login') not in redis.store


def test_login_accepts_account_with_null_status() -> None:
    redis = FakeRedis()
    request = build_request(redis)

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(status=None), None)),
        ),
        patch(f'{GUEST_SERVICE_MODULE}.UserDao.edit_user_dao', new=AsyncMock()),
    ):
        result = asyncio.run(
            GuestAuthService.login(request, FakeSession(), GuestLoginModel(email=TEST_EMAIL, password='Guest@123'))
        )

    # status 为 NULL 的账号必须能登录，且身份依赖侧也必须放行，否则「登录成功、
    # 下一个请求就 401」——两处判定收敛到 is_guest_account_disabled 就是为了这个
    assert result.token


# ---------------------------------------------------------------- 后台闸门


def test_guest_token_is_rejected_by_admin_get_current_user() -> None:
    redis = FakeRedis()
    request = build_request(redis)
    token = asyncio.run(
        LoginService.create_access_token(
            data={'user_id': '88', 'user_name': 'guest_0123456789ab', 'user_type': '01', 'session_id': 'sid-1'}
        )
    )
    redis.store[f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:sid-1'] = token

    with (
        patch(
            f'{LOGIN_SERVICE_MODULE}.UserDao.get_user_by_id',
            new=AsyncMock(return_value={'user_basic_info': build_guest_user()}),
        ),
        pytest.raises(AuthException) as error,
    ):
        asyncio.run(LoginService.get_current_user(request, token, FakeSession()))

    assert error.value.message == '用户token不合法'


def test_guest_account_is_rejected_by_admin_login() -> None:
    redis = FakeRedis()
    request = build_request(redis)
    login_user = UserLogin(userName='guest_0123456789ab', password='Guest@123', captchaEnabled=False)

    with (
        patch(
            f'{LOGIN_SERVICE_MODULE}.login_by_account',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        pytest.raises(LoginException) as error,
    ):
        asyncio.run(LoginService.authenticate_user(request, FakeSession(), login_user))

    # 文案必须与密码错误完全一致，否则可以用来探测访客账号是否存在
    assert error.value.message == '密码错误'


def capture_user_query(coro_factory: Any) -> str:
    """
    执行一次用户列表查询并返回它编译出的SQL文本

    :param coro_factory: 返回待执行协程的工厂函数
    :return: 编译后的SQL文本
    """
    captured: dict[str, Any] = {}

    async def fake_paginate(db: Any, query: Any, page_num: int, page_size: int, is_page: bool) -> list[Any]:
        captured['query'] = query
        return []

    with patch('module_admin.dao.user_dao.PageUtil.paginate', new=fake_paginate):
        asyncio.run(coro_factory())

    return str(captured['query'].compile(compile_kwargs={'literal_binds': True}))


def test_admin_user_list_query_filters_out_guest_users() -> None:
    sql = capture_user_query(lambda: UserDao.get_user_list(None, UserPageQueryModel(), true(), is_page=True))

    assert "sys_user.user_type != '01'" in sql


def test_admin_user_list_query_keeps_users_with_null_user_type() -> None:
    """
    回环根因的回归锁：user_type 为 NULL 的管理员必须留在后台用户列表里。

    后台新建/注册/导入的用户 user_type 实际写入的是显式 NULL（AddUserModel 默认 None，
    add_user_dao 的 SysUser(**model_dump()) 把 None 显式赋到实例上，server_default
    '00' 不生效）。SQL 三值逻辑下 `user_type = '00'` 与 `user_type != '01'` 对 NULL
    都求值为 NULL（等价于假），会把这批管理员从所有管理界面整批抹掉。
    """
    queries = [
        lambda: UserDao.get_user_list(None, UserPageQueryModel(), true(), is_page=True),
        lambda: UserDao.get_user_role_allocated_list_by_role_id(
            None, UserRolePageQueryModel(roleId=2), true(), is_page=True
        ),
        lambda: UserDao.get_user_role_unallocated_list_by_role_id(
            None, UserRolePageQueryModel(roleId=2), true(), is_page=True
        ),
    ]
    for query in queries:
        sql = capture_user_query(query)
        assert 'sys_user.user_type IS NULL' in sql
        assert "sys_user.user_type != '01'" in sql
        # 写成 = '00' 就是本轮回环的根因，必须永久锁死
        assert "sys_user.user_type = '00'" not in sql


def test_admin_login_accepts_user_with_null_user_type() -> None:
    """
    回环根因的回归锁：user_type 为 NULL 的管理员仍能登录后台
    """
    redis = FakeRedis()
    request = build_request(redis)
    login_user = UserLogin(userName='niangao', password='Guest@123', captchaEnabled=False)

    with patch(
        f'{LOGIN_SERVICE_MODULE}.login_by_account',
        new=AsyncMock(return_value=(build_guest_user(user_name='niangao', user_type=None), None)),
    ):
        user = asyncio.run(LoginService.authenticate_user(request, FakeSession(), login_user))

    assert user[0].user_name == 'niangao'


def test_admin_get_current_user_accepts_null_user_type() -> None:
    redis = FakeRedis()
    request = build_request(redis)
    token = asyncio.run(
        LoginService.create_access_token(
            data={'user_id': '2', 'user_name': 'niangao', 'session_id': 'sid-null'},
        )
    )
    # APP_SAME_TIME_LOGIN 为 False 时 key 换成 user_id，两个都写上以免依赖环境配置
    redis.store[f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:sid-null'] = token
    redis.store[f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:2'] = token
    basic_info = SysUser(
        user_id=2,
        user_name='niangao',
        nick_name='年糕',
        user_type=None,
        email='niangao@example.com',
        status='0',
        del_flag='0',
    )

    with patch(
        f'{LOGIN_SERVICE_MODULE}.UserDao.get_user_by_id',
        new=AsyncMock(
            return_value={
                'user_basic_info': basic_info,
                'user_dept_info': None,
                'user_role_info': [],
                'user_post_info': [],
                'user_menu_info': [],
            }
        ),
    ):
        current_user = asyncio.run(LoginService.get_current_user(request, token, FakeSession()))

    assert current_user.user.user_name == 'niangao'


# ---------------------------------------------------------------- bcrypt 72 字节上限


def test_register_rejects_password_over_72_bytes() -> None:
    with pytest.raises(ModelValidatorException) as error:
        build_register_model(password=OVERSIZE_PASSWORD, confirmPassword=OVERSIZE_PASSWORD)

    assert '72' in error.value.message


def test_login_rejects_password_over_72_bytes() -> None:
    with pytest.raises(ModelValidatorException) as error:
        GuestLoginModel(email=TEST_EMAIL, password=OVERSIZE_PASSWORD)

    assert '72' in error.value.message


def test_oversize_password_would_otherwise_crash_bcrypt() -> None:
    """
    佐证上面两条为什么必须在入参层拦：直接喂给 bcrypt 会抛 ValueError 变成 500，
    而兜底 handler 会把英文原文回给匿名调用方
    """
    assert len(OVERSIZE_PASSWORD) <= 50  # noqa: PLR2004
    with pytest.raises(ValueError):
        PwdUtil.get_password_hash(OVERSIZE_PASSWORD)


# ---------------------------------------------------------------- 文本字段校验


def test_register_rejects_blank_username() -> None:
    with pytest.raises(FieldValidationError) as error:
        build_register_model(username='   ')

    assert error.value.message == '用户名不能为空'


def test_register_rejects_script_in_institution() -> None:
    with pytest.raises(FieldValidationError) as error:
        build_register_model(institution='<script>alert(1)</script>')

    assert error.value.message == '所属机构不能包含脚本字符'


def test_register_normalizes_whitespace_only_optional_text() -> None:
    model = build_register_model(institution='   ', position=' 研究员 ')

    assert model.institution is None
    assert model.position == '研究员'


# ---------------------------------------------------------------- Bearer 解析


def test_extract_bearer_token_handles_malformed_headers() -> None:
    assert extract_bearer_token('Bearer abc.def.ghi') == 'abc.def.ghi'
    # RFC 6750 的 scheme 大小写不敏感，小写前缀不能被判成失效 token
    assert extract_bearer_token('bearer abc.def.ghi') == 'abc.def.ghi'
    # 只有前缀没有值：老写法 split(' ')[1] 会 IndexError 变成未捕获的 500
    assert extract_bearer_token('Bearer') is None
    assert extract_bearer_token('Bearer ') is None
    assert extract_bearer_token('BearerXYZ') is None
    assert extract_bearer_token('') is None
    assert extract_bearer_token(None) is None


def test_guest_dependency_returns_401_for_valueless_bearer() -> None:
    redis = FakeRedis()
    request = build_request(redis, headers=[(b'authorization', b'Bearer')])

    with pytest.raises(AuthException) as error:
        asyncio.run(GuestUser()(request, FakeSession()))

    assert error.value.message == '用户未登录，请先完成登录'


def test_guest_dependency_returns_401_for_non_numeric_user_id() -> None:
    redis = FakeRedis()
    token = asyncio.run(
        LoginService.create_access_token(
            data={'user_id': 'not-a-number', 'user_name': 'guest_x', 'user_type': '01', 'session_id': 'sid-2'}
        )
    )
    redis.store[f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:sid-2'] = token
    request = build_request(redis, headers=[(b'authorization', f'bearer {token}'.encode())])

    with pytest.raises(AuthException) as error:
        asyncio.run(GuestUser()(request, FakeSession()))

    # int('not-a-number') 必须在 try 内，否则 ValueError 会变成 500
    assert error.value.message == '用户token已失效，请重新登录'


def test_guest_dependency_accepts_account_with_null_status() -> None:
    redis = FakeRedis()
    token = asyncio.run(
        LoginService.create_access_token(
            data={'user_id': '88', 'user_name': 'guest_x', 'user_type': '01', 'session_id': 'sid-3'}
        )
    )
    redis.store[f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:sid-3'] = token
    request = build_request(redis, headers=[(b'authorization', f'Bearer {token}'.encode())])

    with patch(
        f'{GUEST_ASPECT_MODULE}.GuestProfileDao.get_guest_by_user_id',
        new=AsyncMock(return_value=(build_guest_user(status=None), None)),
    ):
        guest = asyncio.run(GuestUser()(request, FakeSession()))

    assert guest.user_id == 88  # noqa: PLR2004


def test_guest_public_info_hides_user_id() -> None:
    redis = FakeRedis()
    token = asyncio.run(
        LoginService.create_access_token(
            data={'user_id': '88', 'user_name': 'guest_x', 'user_type': '01', 'session_id': 'sid-4'}
        )
    )
    redis.store[f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:sid-4'] = token
    request = build_request(redis, headers=[(b'authorization', f'Bearer {token}'.encode())])

    with patch(
        f'{GUEST_ASPECT_MODULE}.GuestProfileDao.get_guest_by_user_id',
        new=AsyncMock(return_value=(build_guest_user(), None)),
    ):
        guest = asyncio.run(GuestUser()(request, FakeSession()))

    assert set(guest.to_public().model_dump(by_alias=True)) == {'email', 'username', 'institution', 'position'}


# ---------------------------------------------------------------- 登录失败文案一致性


def test_login_unknown_email_and_wrong_code_are_byte_identical() -> None:
    def login_error(guest_row: Any, credential: dict[str, Any]) -> ServiceException:
        redis = FakeRedis()
        request = build_request(redis)
        with (
            patch(
                f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
                new=AsyncMock(return_value=guest_row),
            ),
            pytest.raises(ServiceException) as error,
        ):
            asyncio.run(GuestAuthService.login(request, FakeSession(), GuestLoginModel(email=TEST_EMAIL, **credential)))
        return error.value

    unknown_email = login_error(None, {'code': TEST_CODE})
    wrong_code = login_error((build_guest_user(), None), {'code': TEST_CODE})
    wrong_password = login_error((build_guest_user(), None), {'password': 'WrongPwd'})

    # 五种失败必须逐字节相同：任何差异都是「这个邮箱是不是本站访客」的预言机
    assert unknown_email.message == wrong_code.message == wrong_password.message == '邮箱或密码错误'
    assert unknown_email.data == wrong_code.data == wrong_password.data


# ---------------------------------------------------------------- 验证码自然过期的归因


def test_register_reports_code_expired_when_delete_returns_zero() -> None:
    redis = ExpiringRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)

    with pytest.raises(ServiceException) as error:
        asyncio.run(GuestAuthService.register(request, FakeSession(), build_register_model()))

    # DEL 返回 0 的成因既可能是并发消费也可能是自然过期，不能一律报「该邮箱已注册」：
    # 那会让一个库里根本没有账号的正常用户被告知邮箱已被占用
    assert error.value.message == '验证码错误或已过期'


# ---------------------------------------------------------------- 发码链路


def test_email_code_cooldown_is_written_atomically() -> None:
    redis = FakeRedis()
    request = build_request(redis)

    async def send_twice() -> list[Any]:
        return await asyncio.gather(
            GuestAuthService.send_email_code(
                request, FakeSession(), GuestEmailCodeModel(email=TEST_EMAIL, scene='register')
            ),
            GuestAuthService.send_email_code(
                request, FakeSession(), GuestEmailCodeModel(email=TEST_EMAIL, scene='register')
            ),
            return_exceptions=True,
        )

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.MailService.send_verify_code', new=AsyncMock(return_value=True)) as send_mail,
    ):
        results = asyncio.run(send_twice())

    failed = [item for item in results if isinstance(item, ServiceException)]
    # GET→SET 两步非原子，并发下两个请求都会读到 None 从而一起发信（邮件轰炸 +
    # 验证码互相覆盖）；SET NX 保证恰有一个拿到冷却键
    assert len(failed) == 1
    assert failed[0].message == '发送过于频繁，请稍后再试'
    assert send_mail.await_count == 1


def test_email_code_is_revoked_when_mail_delivery_fails() -> None:
    redis = FakeRedis()
    request = build_request(redis)

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.MailService.send_verify_code', new=AsyncMock(return_value=False)),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(
            GuestAuthService.send_email_code(
                request, FakeSession(), GuestEmailCodeModel(email=TEST_EMAIL, scene='register')
            )
        )

    assert error.value.message == '验证码发送失败，请稍后重试'
    # 信没发出去就不能把码留在 Redis 里：用户拿不到码，那条 key 只会白占 5 分钟
    assert code_key('register') not in redis.store
    # 冷却键同样要撤：否则用户被告知「请稍后重试」，立刻重试却被自己刚写下的冷却键
    # 挡回来报「发送过于频繁」，两条提示互相打架，用户只能干等 60 秒
    assert cd_key('register') not in redis.store


# ---------------------------------------------------------------- Redis 不可用降级


def test_redis_outage_becomes_business_error_not_topology_leak() -> None:
    request = build_request(BrokenRedis())

    with pytest.raises(ServiceException) as error:
        asyncio.run(
            GuestAuthService.send_email_code(
                request, FakeSession(), GuestEmailCodeModel(email=TEST_EMAIL, scene='register')
            )
        )

    assert error.value.message == '服务暂时不可用，请稍后重试'
    assert '6379' not in (error.value.message or '')


def test_redis_outage_in_guest_dependency_becomes_auth_error() -> None:
    token = asyncio.run(
        LoginService.create_access_token(
            data={'user_id': '88', 'user_name': 'guest_x', 'user_type': '01', 'session_id': 'sid-5'}
        )
    )
    request = build_request(BrokenRedis(), headers=[(b'authorization', f'Bearer {token}'.encode())])

    with pytest.raises(AuthException) as error:
        asyncio.run(GuestUser()(request, FakeSession()))

    assert error.value.message == '服务暂时不可用，请稍后重试'
    assert '10.1.2.3' not in (error.value.message or '')


def test_redis_response_error_is_also_treated_as_unavailable() -> None:
    """
    OutOfMemoryError / ReadOnlyError / NoPermissionError / ClusterDownError 都继承自
    ResponseError(RedisError)，与 ConnectionError 之间没有继承关系。只捕连接类异常时，
    「OOM command not allowed when used memory > 'maxmemory'.」会穿透到兜底 handler，
    被 str(exc) 原样回给匿名调用方。
    """
    request = build_request(OomRedis())

    with pytest.raises(ServiceException) as error:
        asyncio.run(
            GuestAuthService.send_email_code(
                request, FakeSession(), GuestEmailCodeModel(email=TEST_EMAIL, scene='register')
            )
        )

    assert error.value.message == '服务暂时不可用，请稍后重试'
    assert 'maxmemory' not in (error.value.message or '')


class OomGetRedis(FakeRedis):
    """
    模拟Redis读取被服务端拒绝（ResponseError 全族）
    """

    async def get(self, key: str) -> str | None:
        raise RedisOutOfMemoryError("OOM command not allowed when used memory > 'maxmemory'.")


def test_redis_response_error_in_guest_dependency_becomes_auth_error() -> None:
    token = asyncio.run(
        LoginService.create_access_token(
            data={'user_id': '88', 'user_name': 'guest_x', 'user_type': '01', 'session_id': 'sid-oom'}
        )
    )
    request = build_request(OomGetRedis(), headers=[(b'authorization', f'Bearer {token}'.encode())])

    with pytest.raises(AuthException) as error:
        asyncio.run(GuestUser()(request, FakeSession()))

    assert error.value.message == '服务暂时不可用，请稍后重试'
    assert 'maxmemory' not in (error.value.message or '')


# ---------------------------------------------------------------- expire_on_commit 陷阱


def test_project_session_factory_really_expires_orm_attributes_after_commit() -> None:
    """
    用项目自己的 session 工厂钉死 expire_on_commit 的语义（本轮 critical 的根因）

    `config/database.py:91` 的 `async_sessionmaker(autocommit=False, autoflush=False,
    bind=engine)` 没传 `expire_on_commit`，取默认 True。这里用同一个工厂 + 一个
    sqlite 内存库复现：commit 之前取的本地变量安然无恙，commit 之后再读同一个属性
    直接抛 MissingGreenlet。之所以要用真引擎而不是替身，是因为这条语义正是替身
    （SimpleNamespace）当初漏掉的那一层。
    """
    probe_base = declarative_base()

    class _ExpireProbe(probe_base):
        __tablename__ = 'expire_probe'

        probe_id = Column(Integer, primary_key=True, autoincrement=True)
        probe_name = Column(String(30))

    async def run_probe() -> tuple[str, Exception | str]:
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        try:
            async with engine.begin() as conn:
                await conn.run_sync(probe_base.metadata.create_all)
            session_local = create_async_session_local(engine)
            assert session_local.kw.get('expire_on_commit', True) is True
            async with session_local() as session:
                row = _ExpireProbe(probe_name='guest_probe')
                session.add(row)
                await session.flush()
                # 正确写法：commit 之前先落成本地变量
                before_commit = row.probe_name
                await session.commit()
                try:
                    # 错误写法：commit 之后再读 ORM 属性
                    after_commit: Exception | str = row.probe_name
                except Exception as e:
                    after_commit = e
            return before_commit, after_commit
        finally:
            await engine.dispose()

    before, after = asyncio.run(run_probe())

    assert before == 'guest_probe'
    assert isinstance(after, MissingGreenlet)


def build_expiring_user(**overrides: Any) -> ExpiringOrmStub:
    """
    构造带ORM过期语义的访客用户替身

    :param overrides: 需要覆盖的字段
    :return: 用户替身
    """
    fields = {
        'user_id': 88,
        'user_name': 'guest_0123456789ab',
        'nick_name': '张三',
        'email': TEST_EMAIL,
        'status': '0',
        'password': PwdUtil.get_password_hash('Guest@123'),
    }
    fields.update(overrides)
    return ExpiringOrmStub(**fields)


def test_register_never_reads_orm_attributes_after_commit() -> None:
    """
    注册成功路径的回归锁：`_create_guest_profile` 内部 commit 之后，代码若再碰
    `user.user_id` / `user.user_name` / `profile.institution`，真实环境就是
    MissingGreenlet —— 两表数据已落库、用户拿不到 token、邮箱被永久占死。
    """
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)
    user = build_expiring_user()
    profile = ExpiringOrmStub(institution='广州中医药大学', position='研究员')
    session = ExpiringSession(user, profile)

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserService.add_user_services', new=AsyncMock()),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(user, None)),
        ),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.add_guest_profile_dao',
            new=AsyncMock(return_value=profile),
        ),
    ):
        result = asyncio.run(GuestAuthService.register(request, session, build_register_model()))

    assert result.token
    assert result.guest.email == TEST_EMAIL
    assert result.guest.username == '张三'
    assert result.guest.institution == '广州中医药大学'
    assert result.guest.position == '研究员'
    assert session.commit_count == 1


def test_login_never_reads_orm_attributes_after_commit() -> None:
    """
    登录成功路径的回归锁：登录审计 commit 之后再读 user/profile 属性，会让一次
    完全正确的登录返回 500
    """
    redis = FakeRedis()
    request = build_request(redis)
    user = build_expiring_user()
    profile = ExpiringOrmStub(institution='机构', position='职位')
    session = ExpiringSession(user, profile)

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(user, profile)),
        ),
        patch(f'{GUEST_SERVICE_MODULE}.UserDao.edit_user_dao', new=AsyncMock()),
    ):
        result = asyncio.run(
            GuestAuthService.login(request, session, GuestLoginModel(email=TEST_EMAIL, password='Guest@123'))
        )

    assert result.token
    assert result.guest.institution == '机构'
    assert result.guest.email == TEST_EMAIL
    assert session.commit_count == 1


def test_register_compensation_survives_rollback_expiring_the_user() -> None:
    """
    最致命的一处：档案写失败 → rollback → 老代码下一行就是
    `logger.error(f'访客{user.user_name}...')`，f-string 求值直接崩，
    `_revoke_guest_user` 从此永不执行，孤儿账号必然产生 —— 上一轮刚修好的根因
    被运行时击穿，而 46 条用例全绿。
    """
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)
    user = build_expiring_user()
    session = ExpiringSession(user)
    revoke = AsyncMock()

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserService.add_user_services', new=AsyncMock()),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(user, None)),
        ),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.add_guest_profile_dao',
            new=AsyncMock(side_effect=RuntimeError('boom')),
        ),
        patch(f'{GUEST_SERVICE_MODULE}.UserDao.delete_user_dao', new=revoke),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(GuestAuthService.register(request, session, build_register_model()))

    assert error.value.message == '注册失败，请稍后重试'
    # 补偿必须真的跑起来，孤儿账号不允许留下
    revoke.assert_awaited_once()
    assert revoke.await_args.args[1].user_id == 88  # noqa: PLR2004


def test_compensation_failure_log_survives_rollback() -> None:
    """
    补偿本身失败时，`rollback()` 之后那行日志要打 user_id / user_name / email ——
    读 ORM 实例的话这行日志会崩，ServiceException 变成 MissingGreenlet 的 500，
    「注册未完成，请联系管理员」这句话永远到不了用户眼前
    """
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)
    user = build_expiring_user()
    session = ExpiringSession(user)

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserService.add_user_services', new=AsyncMock()),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(user, None)),
        ),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.add_guest_profile_dao',
            new=AsyncMock(side_effect=RuntimeError('boom')),
        ),
        patch(f'{GUEST_SERVICE_MODULE}.UserDao.delete_user_dao', new=AsyncMock(side_effect=RuntimeError('gone'))),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(GuestAuthService.register(request, session, build_register_model()))

    assert error.value.message == '注册未完成，请联系管理员'


# ---------------------------------------------------------------- 失败计数的原子性


def test_concurrent_login_failures_are_counted_atomically() -> None:
    """
    GET→SET 两步计数在并发下会互相覆盖，计数永远停在 1，锁定永不触发 —— 攻击者
    只要把请求并发打出去就能完整绕过失败次数限制。INCR 是服务端原子自增。
    """
    redis = FakeRedis()
    request = build_request(redis)
    attempts = CommonConstant.PASSWORD_ERROR_COUNT + 1

    async def run_all() -> list[Any]:
        return await asyncio.gather(
            *[
                GuestAuthService.login(request, FakeSession(), GuestLoginModel(email=TEST_EMAIL, password='WrongPwd'))
                for _ in range(attempts)
            ],
            return_exceptions=True,
        )

    with patch(
        f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
        new=AsyncMock(return_value=(build_guest_user(), None)),
    ):
        results = asyncio.run(run_all())

    assert all(isinstance(item, ServiceException) for item in results)
    assert lock_key('login') in redis.store


def test_login_failure_count_tolerates_garbage_in_redis() -> None:
    """
    脏值（人工写入、key 撞名、旧格式残留）不得变成 500

    老写法先 GET 再 `int(cached_count)`，脏值直接抛 Python 的 ValueError，一路冒到
    兜底 handler 变成 500 并把英文原文回给匿名调用方。改用 INCR 之后，脏值由 Redis
    服务端判定并回 ResponseError，被统一降级成中文业务提示。
    """
    redis = FakeRedis()
    redis.store[fail_key('login')] = 'not-a-number'
    request = build_request(redis)

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email', new=AsyncMock(return_value=None)),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(
            GuestAuthService.login(request, FakeSession(), GuestLoginModel(email=TEST_EMAIL, password='Guest@123'))
        )

    assert error.value.message == '服务暂时不可用，请稍后重试'
    assert 'not an integer' not in (error.value.message or '')


# ---------------------------------------------------------------- 发信失败的 scene 分叉


def test_mail_failure_in_login_scene_keeps_the_silent_response() -> None:
    """
    login 场景下「邮箱不存在」是静默返回成功的。若「邮箱存在但发信失败」返回不同
    文案，攻击者只要等 DirectMail 抖动/额度耗尽，一次请求就能判定任意邮箱是否为
    本站访客 —— 矩阵第 3 行的防枚举投入被整体抵消。
    """
    redis = FakeRedis()
    request = build_request(redis)

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        patch(f'{GUEST_SERVICE_MODULE}.MailService.send_verify_code', new=AsyncMock(return_value=False)),
    ):
        result = asyncio.run(
            GuestAuthService.send_email_code(
                request, FakeSession(), GuestEmailCodeModel(email=TEST_EMAIL, scene='login')
            )
        )

    with patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email', new=AsyncMock(return_value=None)):
        unknown_email_result = asyncio.run(
            GuestAuthService.send_email_code(
                request, FakeSession(), GuestEmailCodeModel(email='nobody@example.com', scene='login')
            )
        )

    # 两种情况必须逐字节相同
    assert result == unknown_email_result == '验证码已发送'
    # 但码与冷却键仍要撤掉：用户收不到信，那两条 key 只会白占位并挡住下一次重试
    assert code_key('login') not in redis.store
    assert cd_key('login') not in redis.store


# ---------------------------------------------------------------- 补偿只认访客维度


def test_guest_user_lookup_is_restricted_to_guest_user_type() -> None:
    session = CapturingSession()

    asyncio.run(GuestProfileDao.get_guest_user_by_email(session, TEST_EMAIL))
    sql = str(session.statements[0].compile(compile_kwargs={'literal_binds': True}))

    # 少了这道过滤，注册前的存在性判断会变成管理员邮箱探测器，
    # 补偿链路则可能软删掉一个与本次注册毫不相干的账号
    assert "sys_user.user_type = '01'" in sql
    assert "sys_user.del_flag = '0'" in sql


def test_compensation_never_revokes_a_non_guest_account() -> None:
    """
    用户已建但按访客维度回查不到时，补偿绝不能退化成「按邮箱全表找一个账号删掉」——
    最坏情况是一个匿名接口把同邮箱的管理员账号软删了
    """
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)
    admin_lookup = AsyncMock(return_value=build_guest_user(user_type='00'))
    revoke = AsyncMock()

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserService.add_user_services', new=AsyncMock()),
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserDao.get_user_by_info', new=admin_lookup),
        patch(f'{GUEST_SERVICE_MODULE}.UserDao.delete_user_dao', new=revoke),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(GuestAuthService.register(request, FakeSession(), build_register_model()))

    assert error.value.message == '注册未完成，请联系管理员'
    admin_lookup.assert_not_awaited()
    revoke.assert_not_awaited()


# ---------------------------------------------------------------- 注册验证码的失败计数


def test_register_locks_email_after_repeated_wrong_codes() -> None:
    """
    register 侧原本对同一枚 6 位码的错误尝试完全不计数：攻击者可用 IP 池爆破受害者
    收到的注册码（5 分钟内 10^6 空间），命中后以自己设定的密码抢注对方邮箱。
    """
    redis = FakeRedis()
    request = build_request(redis)

    for _ in range(CommonConstant.PASSWORD_ERROR_COUNT + 1):
        with pytest.raises(ServiceException) as error:
            asyncio.run(GuestAuthService.register(request, FakeSession(), build_register_model(code='000000')))
        assert error.value.message == '验证码错误或已过期'

    assert lock_key('register') in redis.store
    # 注册侧的锁定不得把受害者的登录一并锁死，否则等于送了一个 DoS 面
    assert lock_key('login') not in redis.store

    # 锁定期内即使猜中了正确的码也走不下去，且文案不变 —— 不额外泄露「被锁了」
    redis.store[code_key('register')] = TEST_CODE
    with pytest.raises(ServiceException) as locked:
        asyncio.run(GuestAuthService.register(request, FakeSession(), build_register_model()))

    assert locked.value.message == '验证码错误或已过期'
    # 锁定期内的请求连码都不消费
    assert redis.store[code_key('register')] == TEST_CODE


def test_register_clears_failure_count_after_valid_code() -> None:
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    redis.store[fail_key('register')] = '3'
    request = build_request(redis)

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserService.add_user_services', new=AsyncMock()),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.add_guest_profile_dao',
            new=AsyncMock(return_value=build_profile()),
        ),
    ):
        asyncio.run(GuestAuthService.register(request, FakeSession(), build_register_model()))

    assert fail_key('register') not in redis.store


# ---------------------------------------------------------------- 注册场景不暴露管理员邮箱


def test_email_code_register_scene_does_not_probe_admin_emails() -> None:
    """
    存在性判断若走全表回查，管理员邮箱同样会得到「该邮箱已注册」，官网匿名接口
    就成了后台管理员邮箱的探测器。只按访客维度判存在。
    """
    redis = FakeRedis()
    request = build_request(redis)
    admin_lookup = AsyncMock(return_value=build_guest_user(user_type='00'))

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserDao.get_user_by_info', new=admin_lookup),
        patch(f'{GUEST_SERVICE_MODULE}.MailService.send_verify_code', new=AsyncMock(return_value=True)),
    ):
        result = asyncio.run(
            GuestAuthService.send_email_code(
                request, FakeSession(), GuestEmailCodeModel(email='admin@example.com', scene='register')
            )
        )

    # 与「全新邮箱」返回完全一致；真正的邮箱冲突留给 add_user_services 的唯一性校验
    assert result == '验证码已发送'
    admin_lookup.assert_not_awaited()


def test_register_email_existence_check_is_guest_scoped() -> None:
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)
    admin_lookup = AsyncMock(return_value=build_guest_user(user_type='00'))

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserDao.get_user_by_info', new=admin_lookup),
        patch(
            f'{GUEST_SERVICE_MODULE}.UserService.add_user_services',
            new=AsyncMock(side_effect=ServiceException(message='新增用户guest_x失败，邮箱账号已存在')),
        ),
        pytest.raises(ServiceException) as error,
    ):
        asyncio.run(GuestAuthService.register(request, FakeSession(), build_register_model()))

    # 管理员邮箱能过存在性检查这一步，但 add_user_services 的唯一性校验仍会拦下，
    # 且文案被统一改写 —— 注册场景本就明确回报邮箱冲突，这是可接受的取舍
    assert error.value.message == '该邮箱已注册'
    admin_lookup.assert_not_awaited()


def test_register_normalizes_email_to_lowercase_before_insert() -> None:
    redis = FakeRedis()
    redis.store[code_key('register')] = TEST_CODE
    request = build_request(redis)
    add_user = AsyncMock()

    with (
        patch(f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_user_by_email', new=AsyncMock(return_value=None)),
        patch(f'{GUEST_SERVICE_MODULE}.UserService.add_user_services', new=add_user),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.add_guest_profile_dao',
            new=AsyncMock(return_value=build_profile()),
        ),
    ):
        asyncio.run(GuestAuthService.register(request, FakeSession(), build_register_model(email='Guest@Example.COM')))

    # get_guest_by_email 用 func.lower() 双侧比对，入库也归一化后数据本身才是干净的
    assert add_user.await_args.args[1].email == TEST_EMAIL


# ---------------------------------------------------------------- 登录审计字段


def test_login_truncates_attacker_controlled_forwarded_ip() -> None:
    """
    login_ip 取自 X-Forwarded-For，长度完全由攻击者控制，超 varchar(128) 会抛
    DataError，原始 SQL 与字段信息经兜底 handler 泄露给匿名接口
    """
    redis = FakeRedis()
    overlong_ip = 'a' * 500
    request = build_request(
        redis,
        headers=[(b'x-forwarded-for', overlong_ip.encode())],
        client=('127.0.0.1', 51234),
    )

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), None)),
        ),
        patch(f'{GUEST_SERVICE_MODULE}.UserDao.edit_user_dao', new=AsyncMock()) as edit_user,
    ):
        result = asyncio.run(
            GuestAuthService.login(request, FakeSession(), GuestLoginModel(email=TEST_EMAIL, password='Guest@123'))
        )

    assert result.token
    assert len(edit_user.await_args.args[1]['login_ip']) == LOGIN_IP_MAX_LENGTH


def test_login_survives_audit_write_failure() -> None:
    """
    凭据已经校验通过，仅仅因为一次审计字段写入失败就让用户登不进来，是把可用性
    押在一个非关键写上；裸 `raise e` 还会把 DB 原始错误透给匿名接口
    """
    redis = FakeRedis()
    request = build_request(redis)
    session = FakeSession()

    with (
        patch(
            f'{GUEST_SERVICE_MODULE}.GuestProfileDao.get_guest_by_email',
            new=AsyncMock(return_value=(build_guest_user(), build_profile())),
        ),
        patch(
            f'{GUEST_SERVICE_MODULE}.UserDao.edit_user_dao',
            new=AsyncMock(side_effect=RuntimeError('value too long for type character varying(128)')),
        ),
    ):
        result = asyncio.run(
            GuestAuthService.login(request, session, GuestLoginModel(email=TEST_EMAIL, password='Guest@123'))
        )

    assert result.token
    assert result.guest.institution == '广州中医药大学'
    assert session.rollback_count == 1


# ---------------------------------------------------------------- 邮件正文与降级开关


def test_mail_body_interpolates_the_expiry_constant() -> None:
    zh = MAIL_TEMPLATES['zh']['body'].format(code=TEST_CODE, minutes=EMAIL_CODE_EXPIRE_MINUTES)
    en = MAIL_TEMPLATES['en']['body'].format(code=TEST_CODE, minutes=EMAIL_CODE_EXPIRE_MINUTES)

    # 常量改了正文不跟着改，会给用户与客服错误信息
    assert f'{EMAIL_CODE_EXPIRE_MINUTES} 分钟内有效' in zh
    assert f'expires in {EMAIL_CODE_EXPIRE_MINUTES} minutes' in en


def test_mail_disabled_degradation_only_applies_to_dev_env() -> None:
    """
    生产漏配 MAIL_ENABLED 时不得静默走「验证码写日志 + 报成功」：故障要靠用户投诉
    才被发现。非 dev 环境下 mail_enabled=False 必须是显式失败。
    """
    with (
        patch('module_action.service.mail_service.MailConfig.mail_enabled', False),
        patch('module_action.service.mail_service.AppConfig.app_env', 'dev'),
    ):
        dev_result = asyncio.run(MailService.send_verify_code(TEST_EMAIL, TEST_CODE, 'zh', expire_minutes=5))

    with (
        patch('module_action.service.mail_service.MailConfig.mail_enabled', False),
        patch('module_action.service.mail_service.AppConfig.app_env', 'prod'),
    ):
        prod_result = asyncio.run(MailService.send_verify_code(TEST_EMAIL, TEST_CODE, 'zh', expire_minutes=5))

    assert dev_result is True
    assert prod_result is False


# ---------------------------------------------------------------- 登出


def build_logout_request(redis: FakeRedis, session_id: str) -> tuple[Request, str]:
    """
    构造一个带合法访客令牌的登出请求

    :param redis: 假Redis实例
    :param session_id: 会话编号
    :return: 请求对象与令牌
    """
    token = asyncio.run(
        LoginService.create_access_token(
            data={'user_id': '88', 'user_name': 'guest_0123456789ab', 'user_type': '01', 'session_id': session_id}
        )
    )

    return build_request(redis, headers=[(b'authorization', f'Bearer {token}'.encode())]), token


def test_logout_revokes_the_redis_session() -> None:
    """
    登出必须真的撤销服务端会话：只清前端 cookie 的话，这张 token 在 Redis 里
    仍然有效，捡到它的人还能继续用满整个有效期
    """
    redis = FakeRedis()
    request, token = build_logout_request(redis, 'sid-logout')
    redis.store[f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:sid-logout'] = token

    result = asyncio.run(GuestAuthService.logout(request))

    assert result == '退出成功'
    assert f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:sid-logout' not in redis.store


def test_logout_is_idempotent_when_session_is_already_gone() -> None:
    """
    幂等：令牌已失效（Redis 里那条会话早被删掉或自然过期）时，重复登出仍报成功。
    这里若抛错，用户会卡在「点了退出却退不出去」的死循环里
    """
    redis = FakeRedis()
    request, token = build_logout_request(redis, 'sid-logout-twice')
    redis.store[f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:sid-logout-twice'] = token

    first = asyncio.run(GuestAuthService.logout(request))
    second = asyncio.run(GuestAuthService.logout(request))

    # 第二次 DEL 返回 0，仍然是成功，且文案与第一次完全一致
    assert first == second == '退出成功'
    assert f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:sid-logout-twice' not in redis.store


def test_logout_succeeds_when_token_cannot_be_parsed() -> None:
    """
    解析不出会话编号（缺 Authorization 头、头畸形、令牌被篡改）一律按已登出处理，
    不能变成 500 也不能变成业务错误
    """
    redis = FakeRedis()
    cases = [
        [],
        [(b'authorization', b'Bearer')],
        [(b'authorization', b'Bearer not-a-jwt')],
    ]

    for headers in cases:
        assert asyncio.run(GuestAuthService.logout(build_request(redis, headers=headers))) == '退出成功'
