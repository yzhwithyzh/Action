from sqlalchemy import Row, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from module_admin.entity.do.dept_do import SysDept
from module_admin.entity.do.user_do import SysUser


async def login_by_account(db: AsyncSession, user_name: str) -> Row[tuple[SysUser, SysDept]] | None:
    """
    根据用户名查询用户信息

    :param db: orm对象
    :param user_name: 用户名
    :return: 用户对象
    """
    user = (
        await db.execute(
            select(SysUser, SysDept)
            # 登录用户名大小写不敏感，与迁移前的 MySQL 行为保持一致
            # （MySQL 默认 utf8mb4_0900_ai_ci 不区分大小写，PostgreSQL 区分）
            .where(func.lower(SysUser.user_name) == func.lower(user_name), SysUser.del_flag == '0')
            .join(
                SysDept,
                and_(SysUser.dept_id == SysDept.dept_id, SysDept.status == '0', SysDept.del_flag == '0'),
                isouter=True,
            )
            .distinct()
        )
    ).first()

    return user
