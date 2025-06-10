import asyncio
import inspect
import json as j
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
    GAME_ID,
    GET_TASK_URL,
    LIKE_URL,
    LOGIN_LOG_URL,
    MR_REFRESH_URL,
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
from ..util import (
    generate_random_ipv4_manual,
    generate_random_string,
    get_public_ip,
    timed_async_cache,
)


async def check_response(
    res: Union[Dict, int],
    token: Optional[str] = None,
    waves_id: Optional[str] = None,
) -> tuple[Optional[Dict], TokenStatus]:
    if not isinstance(res, dict):
        logger.warning(f"[{waves_id}] 系统错误: {res}")
        return None, TokenStatus.ERROR

    res_code = res.get("code")
    res_data = res.get("data", "")
    res_msg = res.get("msg", "") or ""

    if res_code == 200:
        return res_data, TokenStatus.VALID

    logger.warning(f"[RoverSign][{waves_id}] 请求失败 msg:{res_msg} data:{res_data}")

    if res_msg == "请求成功":
        return None, TokenStatus.NOT_REGISTERED
    elif "重新登录" in res_msg or "登录已过期" in res_msg:
        if token and waves_id:
            await WavesUser.mark_cookie_invalid(waves_id, token, "无效")
        elif token:
            await WavesUser.mark_invalid(token, "无效")
        return None, TokenStatus.INVALID
    elif isinstance(res_data, str) and ("denied" in res_data or "RBAC" in res_data):
        return None, TokenStatus.BANNED
    elif res_code == 10902:
        # 新错误。暂不归类。
        return None, TokenStatus.ERROR
    else:
        return None, TokenStatus.UNKNOWN


KURO_VERSION = "2.5.0"


async def get_common_header(platform: str = "ios"):
    devCode = generate_random_string()
    header = {
        "source": platform,
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
        "devCode": devCode,
        "X-Forwarded-For": generate_random_ipv4_manual(),
        "version": KURO_VERSION,
    }
    return header


async def get_headers_ios():
    ip = await get_public_ip()
    header = {
        "source": "ios",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)  KuroGameBox/2.5.0",
        "devCode": f"{ip}, Mozilla/5.0 (iPhone; CPU iPhone OS 18_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)  KuroGameBox/2.5.0",
        "X-Forwarded-For": generate_random_ipv4_manual(),
        "version": KURO_VERSION,  # getPostDetail 需要版本号
    }
    return header


async def get_headers(
    ck: Optional[str] = None,
    platform: Optional[str] = None,
    queryRoleId: Optional[str] = None,
) -> Dict:
    if not ck and not platform:
        return await get_common_header("ios")

    bat = ""
    did = ""
    tokenRoleId = ""
    platform = "ios"
    if ck:
        # 获取当前role信息
        if queryRoleId:
            waves_user = await WavesUser.select_data_by_cookie_and_uid(
                cookie=ck, uid=queryRoleId
            )
            if waves_user:
                platform = waves_user.platform
                bat = waves_user.bat
                did = waves_user.did
                tokenRoleId = waves_user.uid

                logger.debug(
                    f"[RoverSign][get_headers.self.{inspect.stack()[1].function}] [queryRoleId:{queryRoleId} tokenRoleId:{tokenRoleId}] 获取成功: did: {did} bat: {bat}"
                )

        # 2次校验
        if not tokenRoleId:
            waves_user = await WavesUser.select_data_by_cookie(cookie=ck)
            if waves_user:
                platform = waves_user.platform
                bat = waves_user.bat
                did = waves_user.did
                tokenRoleId = waves_user.uid

                logger.debug(
                    f"[RoverSign][get_headers.other.{inspect.stack()[1].function}.2] [queryRoleId:{queryRoleId} tokenRoleId:{tokenRoleId}] 获取成功: did: {did} bat: {bat}"
                )

    if platform == "ios":
        header = await get_headers_ios()
    else:
        header = await get_common_header(platform or "ios")
    if bat:
        header.update({"b-at": bat})
    if did:
        header.update({"did": did})
    return header


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
        bot_id: str,
    ) -> Tuple[Optional[str], TokenStatus]:
        waves_user = await WavesUser.select_waves_user(user_id, waves_id, bot_id)
        if not waves_user or not waves_user.cookie:
            return None, TokenStatus.UNBOUND

        if waves_user.status == "无效":
            return None, TokenStatus.INVALID

        _, token_status = await self.login_log(waves_id, waves_user.cookie)
        if token_status != TokenStatus.VALID:
            return None, token_status

        return await self.refresh_data(waves_id, waves_user.cookie)

    async def refresh_data(
        self,
        waves_id: str,
        token: str,
    ) -> Tuple[Optional[str], TokenStatus]:
        """刷新数据"""
        header = await get_headers(token, queryRoleId=waves_id)
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": SERVER_ID,
            "roleId": waves_id,
        }
        res = await self._waves_request(REFRESH_URL, "POST", header, data=data)

        check_res, check_status = await check_response(res, token, waves_id)
        if not check_res:
            return None, check_status
        else:
            return token, TokenStatus.VALID

    async def login_log(self, roleId: str, token: str):
        header = await get_headers(ck=token, queryRoleId=roleId)
        header.update(
            {
                "token": token,
                "devCode": header.get("did", ""),
                "version": KURO_VERSION,
            }
        )
        header.pop("did", None)
        header.pop("b-at", None)

        data = {}
        res = await self._waves_request(LOGIN_LOG_URL, "POST", header, data=data)
        check_res, check_status = await check_response(res, token, roleId)
        if not check_res:
            return None, check_status
        else:
            return token, TokenStatus.VALID

    async def get_daily_info(
        self, roleId: str, token: str, gameId: Union[str, int] = GAME_ID
    ) -> tuple[Optional[Dict], TokenStatus]:
        """每日"""
        header = await get_headers(token, queryRoleId=roleId)
        header.update({"token": token})
        data = {
            "type": "1",
            "sizeType": "2",
            "gameId": gameId,
            "serverId": self.get_server_id(roleId),
            "roleId": roleId,
        }
        res = await self._waves_request(
            MR_REFRESH_URL,
            "POST",
            header,
            data=data,
        )
        check_res, check_status = await check_response(res, token, roleId)
        if not check_res:
            return None, check_status
        else:
            return check_res, TokenStatus.VALID

    async def sign_in(self, roleId: str, token: str) -> Union[Dict, int]:
        """游戏签到"""
        header = await get_headers(token, queryRoleId=roleId)
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
        header = await get_headers(token, queryRoleId=roleId)
        header.update({"token": token, "devcode": ""})
        data = {
            "gameId": GAME_ID,
            "serverId": SERVER_ID,
            "roleId": roleId,
        }
        return await self._waves_request(
            SIGNIN_TASK_LIST_URL, "POST", header, data=data
        )

    async def get_task(
        self, token: str, roleId: str
    ) -> Optional[Union[Dict, int, str]]:
        try:
            header = await get_headers(token, queryRoleId=roleId)
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
            header = await get_headers(token)
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

    # async def get_gold(self, token: str) -> Optional[Union[Dict, int, str]]:
    #     """获取金币"""
    #     try:
    #         header = await get_headers(token)
    #         header.update({"token": token})
    #         return await self._waves_request(GET_GOLD_URL, "POST", header)
    #     except Exception as e:
    #         logger.exception(f"get_gold token {token}", e)

    async def do_like(
        self, roleId: str, token: str, postId, toUserId
    ) -> Optional[Union[Dict, int, str]]:
        """点赞"""
        try:
            header = await get_headers(token, queryRoleId=roleId)
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

    async def do_sign_in(
        self, roleId: str, token: str
    ) -> Optional[Union[Dict, int, str]]:
        """签到"""
        try:
            header = await get_headers(token, queryRoleId=roleId)
            header.update({"token": token})
            data = {"gameId": "2"}
            return await self._waves_request(SIGN_IN_URL, "POST", header, data=data)
        except Exception as e:
            logger.exception(f"do_sign_in token {token}", e)

    async def do_post_detail(
        self, roleId: str, token: str, postId: str
    ) -> Optional[Union[Dict, int, str]]:
        """浏览"""
        try:
            header = await get_headers(token, queryRoleId=roleId)
            header.update({"token": token})
            data = {
                "postId": postId,
                "showOrderType": "2",
                "isOnlyPublisher": "0",
            }
            if header.get("did"):
                data.update({"devCode": header.get("did", "")})
            return await self._waves_request(POST_DETAIL_URL, "POST", header, data=data)
        except Exception as e:
            logger.exception(f"do_post_detail token {token}", e)

    async def do_share(
        self, roleId: str, token: str
    ) -> Optional[Union[Dict, int, str]]:
        """分享"""
        try:
            header = await get_headers(token, queryRoleId=roleId)
            header.update({"token": token})
            data = {"gameId": "3"}
            return await self._waves_request(SHARE_URL, "POST", header, data=data)
        except Exception as e:
            logger.exception(f"do_share token {token}", e)

    # async def check_bbs_completed(self, token: str, roleId: str) -> bool:
    #     """检查bbs任务是否完成"""
    #     task_res = await self.get_task(token, roleId)
    #     if not isinstance(task_res, dict):
    #         return False
    #     if task_res.get("code") != 200 or not task_res.get("data"):
    #         return False
    #     for i in task_res["data"]["dailyTask"]:
    #         if i["completeTimes"] != i["needActionTimes"]:
    #             return False
    #     return True

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
                        logger.debug(
                            f"url:[{url}] params:[{params}] headers:[{header}] data:[{data}] raw_data:{raw_data}"
                        )
                        return raw_data
            except Exception as e:
                logger.exception(f"url:[{url}] attempt {attempt + 1} failed", e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
        return ROVER_CODE_999
