import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import jwt
from fastapi import Request
from jwt.exceptions import InvalidTokenError
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from common.constant import CommonConstant
from common.enums import RedisInitKeyConfig
from config.env import JwtConfig
from exceptions.exception import ServiceException
from module_action.dao.action_dao import GUEST_USER_TYPE, GuestProfileDao
from module_action.entity.do.action_do import ActionGuestProfile
from module_action.entity.vo.action_vo import (
    GuestEmailCodeModel,
    GuestInfoModel,
    GuestLoginModel,
    GuestRegisterModel,
    GuestTokenModel,
)
from module_action.service.mail_service import MailService
from module_admin.dao.user_dao import UserDao
from module_admin.entity.do.user_do import SysUser
from module_admin.entity.vo.user_vo import AddUserModel, UserModel
from module_admin.service.login_service import LoginService
from module_admin.service.user_service import UserService
from utils.client_ip_util import ClientIPUtil
from utils.log_util import logger
from utils.pwd_util import PwdUtil

# 验证码有效期与同邮箱发送冷却，见 spec-guest-auth.md 的 Boundaries
EMAIL_CODE_EXPIRE_MINUTES = 5
EMAIL_CODE_CD_SECONDS = 60
# 登录失败计数窗口与锁定时长，与后台 login_service 的既有实现保持同一形态
LOGIN_FAIL_WINDOW_MINUTES = 10
# sys_user.login_ip 的列宽（user_do.py:35 varchar(128)）。login_ip 最终取自
# X-Forwarded-For，长度完全由调用方控制，不截断就会抛 DataError，原始 SQL 与字段
# 信息会经兜底 handler 泄露给匿名接口。
LOGIN_IP_MAX_LENGTH = 128
# 登录失败统一文案：账号不存在、账号非访客、验证码错、验证码过期、密码错、
# 失败次数超限——六种情况一律同一句、同一响应码，任何差异都会变成邮箱枚举 oracle
LOGIN_FAILED_MESSAGE = '邮箱或密码错误'
ACCOUNT_DISABLED_MESSAGE = '账号已停用'
EMAIL_REGISTERED_MESSAGE = '该邮箱已注册'
# 「验证码错误或已过期」只允许出现在注册路径
EMAIL_CODE_INVALID_MESSAGE = '验证码错误或已过期'
REGISTER_FAILED_MESSAGE = '注册失败，请稍后重试'
REGISTER_COMPENSATE_FAILED_MESSAGE = '注册未完成，请联系管理员'
MAIL_SEND_FAILED_MESSAGE = '验证码发送失败，请稍后重试'
# 登出统一文案。登出是幂等操作，成功与「本来就没有会话可撤销」共用同一句
LOGOUT_MESSAGE = '退出成功'
# Redis 不可用时对匿名调用方的统一中文提示：绝不能把含 host:port 的原始错误串
# 经兜底 handler（会把 str(exc) 原样回传）泄露给公开接口
REDIS_UNAVAILABLE_MESSAGE = '服务暂时不可用，请稍后重试'
# 补偿失败时打进日志的可检索标记串
COMPENSATE_FAILED_TAG = 'GUEST_REGISTER_COMPENSATE_FAILED'
# 访客账号的停用标记。与 user_type 一样是三态字段：只有明确的 '1' 才算停用，
# NULL 与 '0' 都放行——两处判定一个写 '== 1' 一个写 '!= 0' 时，status 为 NULL 的
# 账号会「登录成功拿到 token，下一个请求就 401」，用户陷入死循环。
GUEST_DISABLED_STATUS = '1'
# 捕获 redis-py 的异常基类，而不只是 ConnectionError/TimeoutError：
# OutOfMemoryError、ReadOnlyError、NoPermissionError、ClusterDownError 都继承自
# ResponseError(RedisError)，与 ConnectionError 无继承关系。只捕连接类异常时，
# 「OOM command not allowed...」「READONLY You can't write against a read only
# replica.」这类服务端错误会穿透到兜底 handler，被原样回给匿名调用方。
REDIS_UNAVAILABLE_ERRORS = (RedisError,)


def is_guest_account_disabled(user: SysUser) -> bool:
    """
    判定访客账号是否已停用（登录闸门与身份依赖共用的唯一判定）

    只拒绝明确的 '1'：status 为 NULL 的历史账号按可用处理，否则两处判定稍有出入
    就会出现「能登录、但下一个请求就 401」的死循环。

    :param user: 访客用户对象
    :return: 已停用返回True
    """
    return user.status == GUEST_DISABLED_STATUS


@dataclass(frozen=True)
class GuestSnapshot:
    """
    访客字段快照（不可变），本模块一切「commit/rollback 之后还要用到的字段」的唯一载体

    本项目的 `async_sessionmaker`（config/database.py:91）未传 `expire_on_commit`，
    取默认值 True：`commit()` 会 `expire_all()` 掉 identity map 里的全部实例，
    `rollback()` 对非嵌套事务同样过期全部实例。此后任何属性读取都会触发惰性刷新，
    在 async 上下文里直接抛 `MissingGreenlet`，并被兜底 handler 以 str(exc) 原样
    回给匿名调用方。修法是**提交前先把字段落成本地快照**（照
    module_admin/service/user_service.py 的既有惯例），而不是去改全局的
    `expire_on_commit`——那是整个项目共用的设置。
    """

    user_id: int
    user_name: str
    email: str
    nick_name: str
    institution: str | None = None
    position: str | None = None

    @classmethod
    def of(cls, user: SysUser, profile: ActionGuestProfile | None = None) -> 'GuestSnapshot':
        """
        从ORM实例摘取快照（必须在任何commit/rollback之前调用）

        :param user: 访客用户对象
        :param profile: 访客档案对象，可能不存在
        :return: 访客字段快照
        """
        return cls(
            user_id=user.user_id,
            user_name=user.user_name or '',
            email=user.email or '',
            nick_name=user.nick_name or '',
            institution=profile.institution if profile else None,
            position=profile.position if profile else None,
        )


class GuestAuthService:
    """
    官网访客账号服务层

    访客与后台系统用户共用 sys_user 表，靠 user_type 区分：'00' 后台、'01' 官网访客。
    访客的 user_name 是 guest_ + 12位随机串（sys_user.user_name 只有 30 字符且与管理员
    共用大小写不敏感的唯一命名空间，用邮箱做 user_name 既会超长又能被用来占位/探测），
    对外的登录标识始终是 email，用户填写的用户名存 nick_name。

    本类的硬性写法约定：**任何 `commit()` / `rollback()` 之后一律不再触碰 ORM 实例**，
    要用的字段一律提前落进 `GuestSnapshot`。理由见 `GuestSnapshot` 的类注释。
    """

    @classmethod
    async def send_email_code(cls, request: Request, query_db: AsyncSession, code_model: GuestEmailCodeModel) -> str:
        """
        发送邮箱验证码service

        :param request: Request对象
        :param query_db: orm对象
        :param code_model: 验证码请求对象
        :return: 提示信息
        """
        email = code_model.email
        scene = code_model.scene
        cd_key = f'{RedisInitKeyConfig.EMAIL_CODE_CD.key}:{scene}:{email.lower()}'
        # 冷却键用 SET NX 原子写入并以返回值判定：先 GET 再 SET 的两步写法在并发下
        # 会让所有请求都读到 None 从而集体绕过频控，对同一邮箱形成邮件轰炸，
        # 后写入的验证码还会把先写入的覆盖掉。
        #
        # 冷却键先落地再做存在性判断：register 场景邮箱已注册会抛异常、login 场景邮箱
        # 不存在会静默成功，若冷却写在这些分支之后，攻击者只要连发两次、看第二次是否
        # 被频控就能反推邮箱是否存在，防枚举形同虚设。
        if not await cls._redis_set(request, cd_key, '1', ex=timedelta(seconds=EMAIL_CODE_CD_SECONDS), nx=True):
            raise ServiceException(message='发送过于频繁，请稍后再试')
        if scene == 'register':
            # 存在性判断只看访客维度：用全表回查会让管理员邮箱同样得到「该邮箱已注册」，
            # 官网匿名接口就成了后台管理员邮箱的探测器。管理员邮箱因此能过这一步，
            # 但真正 add_user_services 时仍会因邮箱唯一性失败——注册场景本就明确回报
            # 邮箱冲突，这是可接受的。
            if await GuestProfileDao.get_guest_user_by_email(query_db, email):
                raise ServiceException(message=EMAIL_REGISTERED_MESSAGE)
        elif not await GuestProfileDao.get_guest_by_email(query_db, email):
            # 登录场景邮箱不存在：不发信、不写验证码，但仍返回成功，防止官网被当成邮箱探测器
            logger.warning(f'邮箱{email}不存在访客账号，登录验证码静默跳过')
            return '验证码已发送'
        code = f'{secrets.randbelow(1000000):06d}'
        code_key = f'{RedisInitKeyConfig.EMAIL_CODE.key}:{scene}:{email.lower()}'
        await cls._redis_set(request, code_key, code, ex=timedelta(minutes=EMAIL_CODE_EXPIRE_MINUTES))
        # 发信结果不能丢：外发失败却报「验证码已发送」，用户会守着一封永远收不到的信。
        # 处理方式按 scene 分叉，见下方注释。
        if not await MailService.send_verify_code(
            email, code, code_model.source_lang, expire_minutes=EMAIL_CODE_EXPIRE_MINUTES
        ):
            # 冷却键必须一并撤销：否则用户收到「请稍后重试」、立刻重试却被自己刚写下的
            # 冷却键挡住报「发送过于频繁」，两条提示互相打架。
            await cls._redis_delete(request, code_key)
            await cls._redis_delete(request, cd_key)
            logger.error(f'邮箱{email}的{scene}验证码外发失败，已撤销刚写入的验证码与冷却键')
            if scene == 'register':
                raise ServiceException(message=MAIL_SEND_FAILED_MESSAGE)
            # login 场景绝不能抛错：该场景下「邮箱不存在」是静默返回成功的（防枚举），
            # 若「邮箱存在但发信失败」返回不同文案，攻击者只要等 DirectMail 抖动或额度
            # 耗尽，一次请求就能判定任意邮箱是否为本站访客，防枚举投入被整体抵消。

        return '验证码已发送'

    @classmethod
    async def register(
        cls, request: Request, query_db: AsyncSession, register_model: GuestRegisterModel
    ) -> GuestTokenModel:
        """
        访客注册service

        :param request: Request对象
        :param query_db: orm对象
        :param register_model: 注册请求对象
        :return: 访客令牌信息
        """
        if register_model.password != register_model.confirm_password:
            raise ServiceException(message='两次输入的密码不一致')
        # 邮箱统一小写入库：get_guest_by_email 走 func.lower() 双侧比对，但库里存的是
        # 用户原样输入，归一化后新建的访客数据本身就是干净的（既有用户数据不动）。
        email = register_model.email.lower()
        # 注册路径同样要有失败计数：只有登录侧计数的话，攻击者可以用 IP 池爆破受害者
        # 收到的那枚 6 位注册码（5 分钟内 10^6 空间），命中后以自己设定的密码抢注对方
        # 邮箱。锁定命中时返回与验证码错误完全相同的文案，不额外泄露「被锁了」。
        if await cls._is_auth_locked(request, 'register', email):
            logger.warning(f'邮箱{email}注册验证码失败次数超限，处于锁定期')
            raise ServiceException(message=EMAIL_CODE_INVALID_MESSAGE)
        # 先消费验证码再查邮箱：这样「注册成功后拿同一枚码再注册一次」拿到的是
        # 「验证码错误或已过期」而不是「该邮箱已注册」，与验收标准一致。
        #
        # 消费失败包含三种成因——码不匹配、key 已不存在、DEL 返回 0（并发消费或在
        # GET 与 DEL 之间自然过期）——一律归到「验证码错误或已过期」。绝不能把 DEL
        # 返回 0 解释成「该邮箱已注册」：码即将过期的正常用户会被告知邮箱已被占用，
        # 而库里根本没有该账号。
        if not await cls._consume_email_code(request, 'register', email, register_model.code):
            await cls._record_auth_failure(request, 'register', email)
            raise ServiceException(message=EMAIL_CODE_INVALID_MESSAGE)
        await cls._clear_auth_failure(request, 'register', email)
        if await GuestProfileDao.get_guest_user_by_email(query_db, email):
            raise ServiceException(message=EMAIL_REGISTERED_MESSAGE)
        now = datetime.now()
        add_user = AddUserModel(
            userName=f'guest_{uuid4().hex[:12]}',
            nickName=register_model.username,
            userType=GUEST_USER_TYPE,
            email=email,
            password=PwdUtil.get_password_hash(register_model.password),
            status='0',
            delFlag='0',
            pwdUpdateDate=now,
            createBy='guest_register',
            createTime=now,
            updateBy='guest_register',
            updateTime=now,
            remark='官网访客注册',
        )
        try:
            await UserService.add_user_services(query_db, add_user)
        except ServiceException as e:
            # add_user_services 的冲突文案带随机 user_name，对官网访客毫无意义，统一改写
            if e.message and '邮箱' in e.message:
                raise ServiceException(message=EMAIL_REGISTERED_MESSAGE) from e
            raise
        guest_row = await GuestProfileDao.get_guest_by_email(query_db, email)
        if guest_row is None:
            # add_user_services 已自行 commit，账号确实落库了却查不回来（主从延迟、
            # 数据被并发改写等）。这里直接抛异常会留下一个永久占用该邮箱、后台用户
            # 列表又看不见（user_type='01' 被过滤）的孤儿账号，必须走补偿撤销。
            logger.error(f'{COMPENSATE_FAILED_TAG} 邮箱{email}的用户已创建但回查不到，尝试撤销')
            await cls._revoke_guest_user_by_email(query_db, email)
            raise ServiceException(message=REGISTER_FAILED_MESSAGE)
        # 快照必须在这里取：紧接着的 _create_guest_profile 会 commit，之后 user 的
        # 所有属性都已过期，再读就是 MissingGreenlet。
        snapshot = GuestSnapshot.of(guest_row[0])
        snapshot = await cls._create_guest_profile(query_db, snapshot, register_model, now)
        token = await cls._create_guest_token(request, snapshot)
        logger.info(f'访客{snapshot.user_name}注册成功')

        return GuestTokenModel(token=token, guest=cls._build_guest_info(snapshot).to_public())

    @classmethod
    async def login(cls, request: Request, query_db: AsyncSession, login_model: GuestLoginModel) -> GuestTokenModel:
        """
        访客登录service（验证码登录与密码登录二选一）

        本方法的所有失败分支——邮箱不存在、账号非访客（get_guest_by_email 已按
        user_type='01' 过滤，管理员邮箱在这里同样查不到）、验证码错、验证码过期、
        密码错、失败次数超限——必须返回完全相同的 message 与响应码。任何一处出现
        「验证码错误或已过期」这类更具体的文案，单次请求就能判定任意邮箱是否为本站
        访客，矩阵第 3 行（登录码静默）的全部防枚举投入会被一并抵消。

        :param request: Request对象
        :param query_db: orm对象
        :param login_model: 登录请求对象
        :return: 访客令牌信息
        """
        email = login_model.email
        # 失败计数与锁定：6 位验证码在 5 分钟存活期内只有 10^6 空间，IP 维度限流
        # 换个 IP 就能线性放大。锁定命中同样返回统一文案，不暴露「这个邮箱被锁了」。
        if await cls._is_auth_locked(request, 'login', email):
            logger.warning(f'邮箱{email}登录失败次数超限，处于锁定期')
            raise ServiceException(message=LOGIN_FAILED_MESSAGE)
        guest_row = await GuestProfileDao.get_guest_by_email(query_db, email)
        if guest_row is None:
            logger.warning(f'邮箱{email}不存在访客账号，官网登录失败')
            # 邮箱不存在也照样计数：只对存在的邮箱计数，会让「第 6 次仍是同一文案」与
            # 「第 6 次被锁」的行为差异重新变成存在性信号。
            await cls._record_auth_failure(request, 'login', email)
            raise ServiceException(message=LOGIN_FAILED_MESSAGE)
        user: SysUser = guest_row[0]
        profile: ActionGuestProfile | None = guest_row[1]
        if login_model.code:
            credential_ok = await cls._consume_email_code(request, 'login', email, login_model.code)
        else:
            credential_ok = bool(PwdUtil.verify_password(login_model.password or '', user.password or ''))
        if not credential_ok:
            logger.warning(f'邮箱{email}官网登录凭据校验失败')
            await cls._record_auth_failure(request, 'login', email)
            raise ServiceException(message=LOGIN_FAILED_MESSAGE)
        await cls._clear_auth_failure(request, 'login', email)
        # 停用判断放在凭据校验之后：否则未持有凭据的人也能靠文案差异探出账号是否存在
        if is_guest_account_disabled(user):
            raise ServiceException(message=ACCOUNT_DISABLED_MESSAGE)
        # 审计写入会 commit，之后 user / profile 的属性全部过期，快照必须先取
        snapshot = GuestSnapshot.of(user, profile)
        await cls._record_login_audit(request, query_db, snapshot.user_id)
        token = await cls._create_guest_token(request, snapshot)
        logger.info(f'访客{snapshot.user_name}登录成功')

        return GuestTokenModel(token=token, guest=cls._build_guest_info(snapshot).to_public())

    @classmethod
    async def logout(cls, request: Request) -> str:
        """
        访客登出service（撤销当前令牌对应的Redis会话）

        本方法**必须幂等**：解析不出会话编号、Redis 里本就没有这个键，一律照常返回
        成功。登出的语义是「让这张 token 不再可用」，只要终态如此就该报成功；任何一条
        失败分支都会把用户卡在「点了退出却退不出去」的死循环里。

        撤销的是 Redis 会话而不是 JWT 本身——JWT 无状态撤销不了，但访客身份依赖每次
        都要拿 `access_token:{session_id}` 回比对（common/aspect/guest_auth.py:119-124），
        键一删这张 token 立刻作废，不必等它自然过期。

        :param request: Request对象
        :return: 提示信息
        """
        session_id = cls._extract_session_id(request)
        if session_id is None:
            logger.warning('访客登出请求未解析出会话编号，按已登出处理')

            return LOGOUT_MESSAGE
        if await cls._redis_delete(request, f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}'):
            logger.info(f'访客会话{session_id}已撤销')
        else:
            # 并发登出、会话自然过期都会走到这里，不是错误
            logger.warning(f'访客会话{session_id}在Redis中已不存在，登出按幂等处理')

        return LOGOUT_MESSAGE

    @classmethod
    def _extract_session_id(cls, request: Request) -> str | None:
        """
        从Authorization请求头解析出访客会话编号

        `extract_bearer_token` 用延迟导入而不是模块顶层导入：`common.aspect.guest_auth`
        在导入时就要从本模块取 `is_guest_account_disabled`，本模块若在顶层反向导入它
        会形成循环导入（那边的 import 排在函数定义之前，必然 ImportError）。

        本方法一律不抛异常：登出是幂等操作，解析失败只意味着「没有可撤销的会话」。

        :param request: Request对象
        :return: 会话编号，解析不出时返回None
        """
        from common.aspect.guest_auth import extract_bearer_token  # noqa: PLC0415

        token = extract_bearer_token(request.headers.get('Authorization'))
        if not token:
            return None
        try:
            payload = jwt.decode(token, JwtConfig.jwt_secret_key, algorithms=[JwtConfig.jwt_algorithm])
        except InvalidTokenError as e:
            logger.warning(f'访客登出请求的令牌无法解析，按已登出处理：{e}')

            return None
        session_id = payload.get('session_id')

        return str(session_id) if session_id else None

    # ------------------------------------------------------------ 验证码与失败计数

    @classmethod
    async def _consume_email_code(
        cls,
        request: Request,
        scene: Literal['register', 'login'],
        email: str,
        code: str,
    ) -> bool:
        """
        校验并立即消费邮箱验证码

        校验通过后立刻 delete，并用 delete 的返回值当互斥量：Redis 的 DEL 是原子的，
        同一枚码只可能有一个请求拿到 1，因此并发同邮箱注册天然只有一个能走下去。
        （现有 captcha_codes 校验后不删是已知缺陷，不照抄。）

        DEL 返回 0 只说明「这枚码已经不在了」，成因既可能是并发消费也可能是在 GET 与
        DEL 之间自然过期，本方法一律返回 False，由调用方按各自路径的统一文案报错。

        :param request: Request对象
        :param scene: 验证码场景
        :param email: 邮箱
        :param code: 用户提交的验证码
        :return: 消费成功返回True
        """
        code_key = f'{RedisInitKeyConfig.EMAIL_CODE.key}:{scene}:{email.lower()}'
        cached_code = await cls._redis_get(request, code_key)
        if not cached_code or str(cached_code) != code:
            logger.warning(f'邮箱{email}的{scene}验证码校验失败')
            return False
        if not await cls._redis_delete(request, code_key):
            logger.warning(f'邮箱{email}的{scene}验证码已被并发消费或恰好过期')
            return False

        return True

    @classmethod
    async def _is_auth_locked(cls, request: Request, scene: Literal['register', 'login'], email: str) -> bool:
        """
        判断邮箱在指定场景下是否处于凭据失败锁定期

        :param request: Request对象
        :param scene: 场景（register注册 login登录）
        :param email: 邮箱
        :return: 处于锁定期返回True
        """
        return bool(await cls._redis_get(request, cls._auth_lock_key(scene, email)))

    @classmethod
    async def _record_auth_failure(cls, request: Request, scene: Literal['register', 'login'], email: str) -> None:
        """
        记录一次凭据失败，超过阈值则锁定该邮箱的该场景

        计数用 Redis 的 INCR 而非「GET 读旧值 → SET 写新值」：后者在两次命令之间没有
        任何互斥，并发失败请求会全部读到同一个旧值再互相覆盖，计数永远停在 1，锁定
        因此永不触发——攻击者只要把请求并发打出去就能完整绕过本防线。INCR 是服务端
        原子自增，顺带也解决了「key 被写进脏值时 int(cached) 抛 ValueError 变 500」。

        窗口 TTL 只在计数从 0 变 1 时设置一次，这样窗口不会被后续失败不断续期。

        :param request: Request对象
        :param scene: 场景（register注册 login登录）
        :param email: 邮箱
        :return: None
        """
        fail_key = cls._auth_fail_key(scene, email)
        fail_count = await cls._redis_incr(request, fail_key)
        if fail_count == 1:
            await cls._redis_expire(request, fail_key, timedelta(minutes=LOGIN_FAIL_WINDOW_MINUTES))
        if fail_count > CommonConstant.PASSWORD_ERROR_COUNT:
            await cls._redis_delete(request, fail_key)
            await cls._redis_set(
                request, cls._auth_lock_key(scene, email), '1', ex=timedelta(minutes=LOGIN_FAIL_WINDOW_MINUTES)
            )
            logger.warning(f'邮箱{email}在{LOGIN_FAIL_WINDOW_MINUTES}分钟内{scene}失败超过阈值，已锁定')

    @classmethod
    async def _clear_auth_failure(cls, request: Request, scene: Literal['register', 'login'], email: str) -> None:
        """
        凭据校验通过后清空失败计数

        :param request: Request对象
        :param scene: 场景（register注册 login登录）
        :param email: 邮箱
        :return: None
        """
        await cls._redis_delete(request, cls._auth_fail_key(scene, email))

    @classmethod
    def _auth_fail_key(cls, scene: Literal['register', 'login'], email: str) -> str:
        """
        构造凭据失败计数的Redis键

        键里带 scene：注册与登录共用一个计数器的话，攻击者只要对受害者邮箱连发几次
        错误的注册码，就能把对方的登录一并锁死 10 分钟，等于送了一个 DoS 面。

        :param scene: 场景（register注册 login登录）
        :param email: 邮箱
        :return: Redis键
        """
        return f'{RedisInitKeyConfig.GUEST_LOGIN_FAIL.key}:{scene}:{email.lower()}'

    @classmethod
    def _auth_lock_key(cls, scene: Literal['register', 'login'], email: str) -> str:
        """
        构造凭据失败锁定的Redis键

        :param scene: 场景（register注册 login登录）
        :param email: 邮箱
        :return: Redis键
        """
        return f'{RedisInitKeyConfig.GUEST_LOGIN_LOCK.key}:{scene}:{email.lower()}'

    # ------------------------------------------------------------ 注册补偿

    @classmethod
    async def _create_guest_profile(
        cls, query_db: AsyncSession, snapshot: GuestSnapshot, register_model: GuestRegisterModel, now: datetime
    ) -> GuestSnapshot:
        """
        写入访客档案，失败时回滚并撤销刚创建的用户

        `UserService.add_user_services` 自己提交，档案写在它之后就无法靠同一个事务回滚，
        物理上做不到「任一步失败整体 rollback」，只能补偿式撤销：把刚建的 sys_user
        逻辑删除掉，既不留「有账号没档案」的半成品，也把邮箱释放出来供重新注册。

        入参与返回值都是不可变快照而不是 ORM 实例：本方法内部会 commit / rollback，
        两者都会过期 identity map 里的全部实例，之后（包括 except 分支里的那行日志）
        再碰 ORM 属性就是 MissingGreenlet——补偿逻辑会在第一行 f-string 上崩掉，
        `_revoke_guest_user` 从此永不执行，孤儿账号必然产生。

        :param query_db: orm对象
        :param snapshot: 刚创建的用户快照
        :param register_model: 注册请求对象
        :param now: 注册时间
        :return: 补齐机构/职位后的访客快照
        """
        try:
            profile = await GuestProfileDao.add_guest_profile_dao(
                query_db,
                {
                    'user_id': snapshot.user_id,
                    'institution': register_model.institution or '',
                    'position': register_model.position or '',
                    'del_flag': '0',
                    'create_time': now,
                    'update_time': now,
                },
            )
            # 直接用 DAO 返回的对象取值，不再 commit 后回查一次：既省一次 SELECT，
            # 也避免主从架构下回查命中延迟从库返回 None、让用户刚填的机构/职位在
            # 注册响应里显示为空。取值必须排在 commit 之前。
            institution, position = profile.institution, profile.position
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            logger.error(f'访客{snapshot.user_name}档案写入失败，回滚已创建的账号：{e}')
            # 补偿本身失败会抛 ServiceException（文案「注册未完成，请联系管理员」），
            # 在这里刻意不吞掉：孤儿账号必须让用户与运维都立刻知道。
            await cls._revoke_guest_user(query_db, snapshot)
            raise ServiceException(message=REGISTER_FAILED_MESSAGE) from e

        return replace(snapshot, institution=institution, position=position)

    @classmethod
    async def _revoke_guest_user_by_email(cls, query_db: AsyncSession, email: str) -> None:
        """
        按邮箱定位并撤销注册中途失败的访客用户

        回查走 `GuestProfileDao.get_guest_user_by_email`（带 user_type='01' 过滤）而不是
        `UserDao.get_user_by_info`：后者不区分账号体系，补偿有可能软删掉一个与本次注册
        毫不相干的账号——最坏情况是管理员账号被一个匿名接口触发封禁。

        :param query_db: orm对象
        :param email: 邮箱
        :return: None
        :raise: 补偿失败时抛ServiceException
        """
        created_user = await GuestProfileDao.get_guest_user_by_email(query_db, email)
        if created_user is None:
            logger.error(f'{COMPENSATE_FAILED_TAG} 邮箱{email}的用户既查不到访客身份也查不到用户本身，需人工核查')
            raise ServiceException(message=REGISTER_COMPENSATE_FAILED_MESSAGE)
        await cls._revoke_guest_user(query_db, GuestSnapshot.of(created_user))

    @classmethod
    async def _revoke_guest_user(cls, query_db: AsyncSession, snapshot: GuestSnapshot) -> None:
        """
        撤销注册中途失败的访客用户（补偿操作）

        补偿失败**不得只写日志静默返回**：那会留下一个永久占用该邮箱、后台用户列表
        又看不见的孤儿账号，用户既没法用也没法重注册，且无从排查。

        入参是快照而非 ORM 实例：本方法既可能在 `_create_guest_profile` 已经 rollback
        之后被调用，自身 except 分支里的日志又排在 `rollback()` 之后，两处都不能再有
        任何 ORM 属性读取。

        :param query_db: orm对象
        :param snapshot: 需要撤销的用户快照
        :return: None
        :raise: 补偿失败时抛ServiceException
        """
        try:
            await UserDao.delete_user_dao(
                query_db,
                UserModel(userId=snapshot.user_id, updateBy='guest_register', updateTime=datetime.now()),
            )
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            logger.error(
                f'{COMPENSATE_FAILED_TAG} 撤销访客用户失败，需人工清理：'
                f'user_id={snapshot.user_id} user_name={snapshot.user_name} email={snapshot.email} 原因={e}'
            )
            raise ServiceException(message=REGISTER_COMPENSATE_FAILED_MESSAGE) from e

    # ------------------------------------------------------------ 登录审计

    @classmethod
    async def _record_login_audit(cls, request: Request, query_db: AsyncSession, user_id: int) -> None:
        """
        写入最后登录时间与IP（审计字段），失败只记日志、不阻断登录

        两处防线：
        1. login_ip 按 sys_user.login_ip 的列宽截断。它最终取自 X-Forwarded-For，
           长度完全由攻击者控制，超 varchar(128) 会抛 DataError，原始 SQL 与字段信息
           会被兜底 handler 以 str(exc) 原样回给匿名接口。
        2. 写失败只记日志。凭据已经校验通过，仅仅因为一次审计字段写入失败就让用户
           登不进来，是把可用性押在一个非关键写上。

        :param request: Request对象
        :param query_db: orm对象
        :param user_id: 访客用户id
        :return: None
        """
        try:
            login_ip = (ClientIPUtil.get_client_ip(request) or '')[:LOGIN_IP_MAX_LENGTH]
            await UserDao.edit_user_dao(
                query_db,
                {'user_id': user_id, 'login_date': datetime.now(), 'login_ip': login_ip},
            )
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()
            logger.error(f'访客user_id={user_id}的登录审计字段写入失败，不阻断本次登录：{e}')

    # ------------------------------------------------------------ 令牌与组装

    @classmethod
    async def _create_guest_token(cls, request: Request, snapshot: GuestSnapshot) -> str:
        """
        创建访客令牌并写入Redis

        payload 里的 user_type 是访客身份依赖唯一认的标记；访客固定按 session_id 存
        Redis，不跟随 APP_SAME_TIME_LOGIN，官网多设备登录是常态。

        入参是快照而非 ORM 实例：本方法的两个调用点都排在 commit 之后。

        :param request: Request对象
        :param snapshot: 访客快照
        :return: 访客令牌
        """
        session_id = str(uuid4())
        access_token = await LoginService.create_access_token(
            data={
                'user_id': str(snapshot.user_id),
                'user_name': snapshot.user_name,
                'user_type': GUEST_USER_TYPE,
                'session_id': session_id,
            },
            expires_delta=timedelta(minutes=JwtConfig.jwt_expire_minutes),
        )
        await cls._redis_set(
            request,
            f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}',
            access_token,
            ex=timedelta(minutes=JwtConfig.jwt_redis_expire_minutes),
        )

        return access_token

    @classmethod
    def _build_guest_info(cls, snapshot: GuestSnapshot) -> GuestInfoModel:
        """
        组装访客信息

        :param snapshot: 访客快照
        :return: 访客信息
        """
        return GuestInfoModel(
            userId=snapshot.user_id,
            email=snapshot.email,
            username=snapshot.nick_name,
            institution=snapshot.institution,
            position=snapshot.position,
        )

    # ------------------------------------------------------------ Redis 访问封装
    #
    # 本类所有 redis 调用一律走下面几个封装：redis-py 的错误串里带 host:port 或
    # 「OOM command not allowed when used memory > 'maxmemory'」这类服务端细节，
    # 直接冒泡会被兜底 handler 的 str(exc) 原样回给匿名调用方，等于向公网泄露内部
    # 拓扑与运行状态。限流层已按 fail_strategy='local_fallback' 考虑过 Redis 挂掉，
    # 业务层不能没考虑。

    @classmethod
    async def _redis_get(cls, request: Request, key: str) -> str | None:
        """
        读取Redis键值，Redis不可用时降级为中文业务异常

        :param request: Request对象
        :param key: Redis键
        :return: 键值，不存在时返回None
        """
        try:
            return await request.app.state.redis.get(key)
        except REDIS_UNAVAILABLE_ERRORS as e:
            logger.error(f'Redis不可用，读取{key}失败：{e}')
            raise ServiceException(message=REDIS_UNAVAILABLE_MESSAGE) from e

    @classmethod
    async def _redis_set(
        cls, request: Request, key: str, value: str, ex: timedelta | None = None, nx: bool = False
    ) -> Any:
        """
        写入Redis键值，Redis不可用时降级为中文业务异常

        :param request: Request对象
        :param key: Redis键
        :param value: 键值
        :param ex: 过期时间
        :param nx: 是否仅在键不存在时写入
        :return: Redis的写入结果（nx未命中时为假值）
        """
        try:
            if nx:
                return await request.app.state.redis.set(key, value, ex=ex, nx=True)
            return await request.app.state.redis.set(key, value, ex=ex)
        except REDIS_UNAVAILABLE_ERRORS as e:
            logger.error(f'Redis不可用，写入{key}失败：{e}')
            raise ServiceException(message=REDIS_UNAVAILABLE_MESSAGE) from e

    @classmethod
    async def _redis_incr(cls, request: Request, key: str) -> int:
        """
        原子自增Redis计数，Redis不可用时降级为中文业务异常

        :param request: Request对象
        :param key: Redis键
        :return: 自增后的计数值
        """
        try:
            return int(await request.app.state.redis.incr(key))
        except REDIS_UNAVAILABLE_ERRORS as e:
            logger.error(f'Redis不可用，自增{key}失败：{e}')
            raise ServiceException(message=REDIS_UNAVAILABLE_MESSAGE) from e

    @classmethod
    async def _redis_expire(cls, request: Request, key: str, ex: timedelta) -> None:
        """
        设置Redis键的过期时间，Redis不可用时降级为中文业务异常

        :param request: Request对象
        :param key: Redis键
        :param ex: 过期时间
        :return: None
        """
        try:
            await request.app.state.redis.expire(key, ex)
        except REDIS_UNAVAILABLE_ERRORS as e:
            logger.error(f'Redis不可用，设置{key}过期时间失败：{e}')
            raise ServiceException(message=REDIS_UNAVAILABLE_MESSAGE) from e

    @classmethod
    async def _redis_delete(cls, request: Request, key: str) -> int:
        """
        删除Redis键，Redis不可用时降级为中文业务异常

        :param request: Request对象
        :param key: Redis键
        :return: 实际删除的键数量
        """
        try:
            return await request.app.state.redis.delete(key)
        except REDIS_UNAVAILABLE_ERRORS as e:
            logger.error(f'Redis不可用，删除{key}失败：{e}')
            raise ServiceException(message=REDIS_UNAVAILABLE_MESSAGE) from e
