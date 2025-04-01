from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlalchemy import null
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, select

from gsuid_core.utils.database.base_models import (
    Bind,
    User,
    with_session,
)

T_WavesBind = TypeVar("T_WavesBind", bound="WavesBind")
T_WavesUser = TypeVar("T_WavesUser", bound="WavesUser")


class WavesBind(Bind, table=True):
    __table_args__: Dict[str, Any] = {"extend_existing": True}
    uid: Optional[str] = Field(default=None, title="鸣潮UID")


class WavesUser(User, table=True):
    __table_args__: Dict[str, Any] = {"extend_existing": True}
    cookie: str = Field(default="", title="Cookie")
    uid: str = Field(default=None, title="鸣潮UID")
    record_id: Optional[str] = Field(default=None, title="鸣潮记录ID")
    platform: str = Field(default="", title="ck平台")
    stamina_bg_value: str = Field(default="", title="体力背景")
    bbs_sign_switch: str = Field(default="off", title="自动社区签到")

    @classmethod
    @with_session
    async def select_cookie(
        cls: Type[T_WavesUser],
        session: AsyncSession,
        user_id: str,
        waves_id: str,
    ) -> Optional[str]:
        """
        根据用户ID和鸣潮UID查询cookie
        """
        sql = (
            select(cls)
            .where(cls.user_id == user_id)
            .where(cls.uid == waves_id)
        )
        result = await session.execute(sql)
        data = result.scalars().all()
        return data[0].cookie if data else None

    @classmethod
    @with_session
    async def select_data_by_cookie(
        cls: Type[T_WavesUser],
        session: AsyncSession,
        cookie: str,
    ) -> Optional[T_WavesUser]:
        """
        根据cookie查询数据
        """
        sql = select(cls).where(cls.cookie == cookie)
        result = await session.execute(sql)
        data = result.scalars().all()
        return data[0] if data else None

    @classmethod
    @with_session
    async def get_waves_all_user(
        cls: Type[T_WavesUser],
        session: AsyncSession,
    ) -> List[T_WavesUser]:
        """
        获取有cookie的玩家。
        """
        sql = (
            select(cls)
            .where(cls.cookie != null())
            .where(cls.cookie != "")
            .where(cls.user_id != null())
            .where(cls.user_id != "")
        )
        result = await session.execute(sql)
        data = result.scalars().all()
        return list(data)
