import asyncio
import copy
import json as j
import uuid
from datetime import datetime
from typing import Any, Dict, Literal, Optional, Tuple, Union

from aiohttp import (
    ClientSession,
    ClientTimeout,
    ContentTypeError,
    FormData,
    TCPConnector,
)

from gsuid_core.logger import logger

from ..api.api import (
    FORUM_LIST_URL,
    GAME_DATA_URL,
    GAME_ID,
    GET_GOLD_URL,
    GET_TASK_URL,
    LIKE_URL,
    POST_DETAIL_URL,
    REFRESH_URL,
    SERVER_ID,
    SERVER_ID_NET,
    SHARE_URL,
    SIGN_IN_URL,
    SIGNIN_TASK_LIST_URL,
    SIGNIN_URL,
    get_local_proxy_url,
)
from ..constant import TokenStatus
from ..database.models import WavesUser
from ..errors import ROVER_CODE_999
from ..util import generate_random_string, timed_async_cache


async def check_response(
    res: Union[Dict, int],
    waves_id: Optional[str] = None,
) -> tuple[Optional[Dict], TokenStatus]:
    if not isinstance(res, dict):
        logger.warning(f"[{waves_id}] 系统错误: {res}")
        return None, TokenStatus.ERROR

    res_code = res.get("code")
    res_data = res.get("data", "")
    res_msg = res.get("msg", "")

    if res_code == 200:
        return res_data, TokenStatus.VALID

    logger.warning(f"[{waves_id}] 请求失败 msg:{res_msg} data:{res_data}")

    if res_msg == "请求成功":
        return None, TokenStatus.NOT_REGISTERED
    elif "重新登录" in res_msg or "登录已过期" in res_msg:
        return None, TokenStatus.INVALID
    elif "denied" in res_data or "RBAC" in res_data:
        return None, TokenStatus.BANNED
    else:
        return None, TokenStatus.UNKNOWN


async def get_headers_h5():
    devCode = generate_random_string()
    header = {
        "source": "h5",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
        "devCode": devCode,
        "version": "2.5.0",
    }
    return header


async def get_headers_ios():
    devCode = uuid.uuid4()
    header = {
        "source": "ios",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": "KuroGameBox/1 CFNetwork/3826.500.111.2.2 Darwin/24.4.0",
        "devCode": f"{devCode}",
        "version": "2.5.0",
    }
    return header


async def get_headers(ck: Optional[str] = None, platform: Optional[str] = None):
    if ck and not platform:
        try:
            waves_user: Optional[WavesUser] = await WavesUser.select_data_by_cookie(
                cookie=ck
            )
            platform = waves_user.platform if waves_user else "h5"
        except Exception as _:
            pass
    if platform == "h5" or not platform:
        return await get_headers_h5()
    elif platform == "ios":
        return await get_headers_ios()

    return await get_headers_h5()


class RoverRequest:
    ssl_verify = True

    def is_net(self, roleId):
        _temp = int(roleId)
        return _temp >= 200000000

    def get_server_id(self, roleId, serverId: Optional[str] = None):
        if serverId:
            return serverId
        if self.is_net(roleId):
            return SERVER_ID_NET
        else:
            return SERVER_ID

    async def get_self_token(
        self,
        waves_id: str,
        user_id: str,
    ) -> Tuple[Optional[str], TokenStatus]:
        cookie = await WavesUser.select_cookie(user_id, waves_id)
        if not cookie:
            return None, TokenStatus.UNBOUND

        if not await WavesUser.cookie_validate(waves_id):
            return None, TokenStatus.INVALID

        return await self.refresh_data(waves_id, cookie)

    async def refresh_data(
        self,
        waves_id: str,
        token: str,
    ) -> Tuple[Optional[str], TokenStatus]:
        """刷新数据"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": SERVER_ID,
            "roleId": waves_id,
        }
        res = await self._waves_request(REFRESH_URL, "POST", header, data=data)

        check_res, check_status = await check_response(res, waves_id)
        if check_res is None:
            if check_status == TokenStatus.INVALID:
                await WavesUser.mark_invalid(token, "无效")
            return None, check_status
        else:
            return token, TokenStatus.VALID

    async def get_daily_info(
        self, roleId: str, token: str, gameId: Union[str, int] = GAME_ID
    ) -> tuple[Optional[Dict], TokenStatus]:
        """每日"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "type": "2",
            "sizeType": "1",
            "gameId": gameId,
            "serverId": self.get_server_id(roleId),
            "roleId": roleId,
        }
        res = await self._waves_request(
            GAME_DATA_URL,
            "POST",
            header,
            data=data,
        )
        check_res, check_status = await check_response(res)
        if not check_res:
            return None, check_status
        else:
            return check_res, TokenStatus.VALID

    async def sign_in(self, roleId: str, token: str) -> Union[Dict, int]:
        """游戏签到"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token, "devcode": ""})
        data = {
            "gameId": GAME_ID,
            "serverId": SERVER_ID,
            "roleId": roleId,
            "reqMonth": f"{datetime.now().month:02}",
        }
        return await self._waves_request(SIGNIN_URL, "POST", header, data=data)

    async def sign_in_task_list(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> Union[Dict, int]:
        """游戏签到"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token, "devcode": ""})
        data = {
            "gameId": GAME_ID,
            "serverId": SERVER_ID,
            "roleId": roleId,
        }
        return await self._waves_request(
            SIGNIN_TASK_LIST_URL, "POST", header, data=data
        )

    async def get_task(self, token: str) -> Optional[Union[Dict, int, str]]:
        try:
            header = copy.deepcopy(await get_headers(token))
            header.update({"token": token})
            data = {"gameId": "0"}
            return await self._waves_request(GET_TASK_URL, "POST", header, data=data)
        except Exception as e:
            logger.exception(f"get_task token {token}", e)

    @timed_async_cache(
        3600,
        lambda x: x and isinstance(x, dict) and x.get("code") == 200,
    )
    async def get_form_list(self, token: str) -> Optional[Union[Dict, int, str]]:
        try:
            header = copy.deepcopy(await get_headers(token))
            header.update({"token": token, "version": "2.25"})
            data = {
                "pageIndex": "1",
                "pageSize": "20",
                "timeType": "0",
                "searchType": "1",
                "forumId": "9",
                "gameId": "3",
            }
            return await self._waves_request(FORUM_LIST_URL, "POST", header, data=data)
        except Exception as e:
            logger.exception(f"get_form_list token {token}", e)

    async def get_gold(self, token: str) -> Optional[Union[Dict, int, str]]:
        """获取金币"""
        try:
            header = copy.deepcopy(await get_headers(token))
            header.update({"token": token})
            return await self._waves_request(GET_GOLD_URL, "POST", header)
        except Exception as e:
            logger.exception(f"get_gold token {token}", e)

    async def do_like(
        self, token: str, postId, toUserId
    ) -> Optional[Union[Dict, int, str]]:
        """点赞"""
        try:
            header = copy.deepcopy(await get_headers(token))
            header.update({"token": token})
            data = {
                "gameId": "3",  # 鸣潮
                "likeType": "1",  # 1.点赞帖子 2.评论
                "operateType": "1",  # 1.点赞 2.取消
                "postId": postId,
                "toUserId": toUserId,
            }
            return await self._waves_request(LIKE_URL, "POST", header, data=data)
        except Exception as e:
            logger.exception(f"do_like token {token}", e)

    async def do_sign_in(self, token: str) -> Optional[Union[Dict, int, str]]:
        """签到"""
        try:
            header = copy.deepcopy(await get_headers(token))
            header.update({"token": token})
            data = {"gameId": "2"}
            return await self._waves_request(SIGN_IN_URL, "POST", header, data=data)
        except Exception as e:
            logger.exception(f"do_sign_in token {token}", e)

    async def do_post_detail(
        self, token: str, postId: str
    ) -> Optional[Union[Dict, int, str]]:
        """浏览"""
        try:
            header = copy.deepcopy(await get_headers(token))
            header.update({"token": token})
            data = {
                "postId": postId,
                "showOrderType": "2",
                "isOnlyPublisher": "0",
            }
            return await self._waves_request(POST_DETAIL_URL, "POST", header, data=data)
        except Exception as e:
            logger.exception(f"do_post_detail token {token}", e)

    async def do_share(self, token: str) -> Optional[Union[Dict, int, str]]:
        """分享"""
        try:
            header = copy.deepcopy(await get_headers(token))
            header.update({"token": token})
            data = {"gameId": "3"}
            return await self._waves_request(SHARE_URL, "POST", header, data=data)
        except Exception as e:
            logger.exception(f"do_share token {token}", e)

    async def check_bbs_completed(self, token: str) -> bool:
        """检查bbs任务是否完成"""
        task_res = await self.get_task(token)
        if not isinstance(task_res, dict):
            return False
        if task_res.get("code") != 200 or not task_res.get("data"):
            return False
        for i in task_res["data"]["dailyTask"]:
            if i["completeTimes"] != i["needActionTimes"]:
                return False
        return True

    async def _waves_request(
        self,
        url: str,
        method: Literal["GET", "POST"] = "GET",
        header=None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[FormData, Dict[str, Any]]] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Union[Dict, int]:
        if header is None:
            header = await get_headers()

        proxy_url = get_local_proxy_url()

        for attempt in range(max_retries):
            try:
                async with ClientSession(
                    connector=TCPConnector(verify_ssl=self.ssl_verify)
                ) as client:
                    async with client.request(
                        method,
                        url=url,
                        headers=header,
                        params=params,
                        json=json,
                        data=data,
                        proxy=proxy_url,
                        timeout=ClientTimeout(10),
                    ) as resp:
                        try:
                            raw_data = await resp.json()
                        except ContentTypeError:
                            _raw_data = await resp.text()
                            raw_data = {
                                "code": ROVER_CODE_999,
                                "data": _raw_data,
                            }
                        if (
                            isinstance(raw_data, dict)
                            and "data" in raw_data
                            and isinstance(raw_data["data"], str)
                        ):
                            try:
                                des_data = j.loads(raw_data["data"])
                                raw_data["data"] = des_data
                            except Exception:
                                pass
                        logger.debug(f"url:[{url}] raw_data:{raw_data}")
                        return raw_data
            except Exception as e:
                logger.exception(f"url:[{url}] attempt {attempt + 1} failed", e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
        return ROVER_CODE_999
