from plugins.RoverSign.RoverSign.utils.constant import BoardcastTypeEnum

from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.subscribe import gs_subscribe

from ..utils.database.models import WavesUser


async def get_signin_config():
    from .roversign_config import RoverSignConfig

    master = RoverSignConfig.get_config("SigninMaster").data
    signin = RoverSignConfig.get_config("SchedSignin").data
    return master or signin


async def get_bbs_signin_config():
    from .roversign_config import RoverSignConfig

    master = RoverSignConfig.get_config("SigninMaster").data
    signin = RoverSignConfig.get_config("BBSSchedSignin").data

    return master or signin


async def set_config_func(ev: Event, uid: str = "0"):
    config_name = ev.text
    if "开启" in ev.command:
        option = ev.group_id if ev.group_id else "on"
    else:
        option = "off"

    logger.info(f"uid: {uid}, option: {option}, config_name: {config_name}")

    other_msg = ""
    if config_name == "自动签到":
        if not await get_signin_config():
            return "自动签到功能已禁用!\n"

        # 执行设置
        await WavesUser.update_data_by_uid(
            uid=uid,
            bot_id=ev.bot_id,
            **{
                "sign_switch": option,
                "bbs_sign_switch": option,
            },
        )

        if option == "off":
            await gs_subscribe.delete_subscribe(
                "single", BoardcastTypeEnum.SIGN_RESULT, ev
            )
        else:
            await gs_subscribe.add_subscribe(
                "single", BoardcastTypeEnum.SIGN_RESULT, ev
            )
            from .roversign_config import RoverSignConfig

            SIGN_TIME = RoverSignConfig.get_config("SignTime").data
            other_msg = f"😄将于[{SIGN_TIME[0]}:{SIGN_TIME[1]}]点自动为您开始{config_name}"
    else:
        return "该配置项不存在!"

    if option == "on":
        succeed_msg = "开启至私聊消息!"
    elif option == "off":
        succeed_msg = "关闭!"
    else:
        succeed_msg = f"开启至群{option}"

    return f"{config_name}已{succeed_msg}\n{other_msg}"
