from gsuid_core.aps import scheduler
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.subscribe import gs_subscribe
from gsuid_core.sv import SV

from ..roversign_config.roversign_config import RoverSignConfig
from ..utils.constant import BoardcastTypeEnum
from .new_sign import rover_auto_sign_task, rover_sign_up_handler

sv_waves_sign = SV("RoverSign-签到", priority=1)
waves_sign_all = SV("RoverSign-全部签到", pm=1)

# 签到时间
SIGN_TIME = RoverSignConfig.get_config("SignTime").data


@sv_waves_sign.on_fullmatch(
    (
        "签到",
        "社区签到",
        "每日任务",
        "社区任务",
        "库街区签到",
        "sign",
    ),
    block=True,
)
async def rover_user_sign(bot: Bot, ev: Event):
    msg = await rover_sign_up_handler(bot, ev)
    return await bot.send(msg)


@scheduler.scheduled_job("cron", hour=SIGN_TIME[0], minute=SIGN_TIME[1])
async def rover_auto_sign():
    msg = await rover_auto_sign_task()
    subscribes = await gs_subscribe.get_subscribe(
        BoardcastTypeEnum.SIGN_RESULT
    )
    if subscribes:
        logger.info(f"[RoverSign]推送主人签到结果: {msg}")
        for sub in subscribes:
            await sub.send(msg)


@waves_sign_all.on_fullmatch(("全部签到"))
async def rover_sign_recheck_all(bot: Bot, ev: Event):
    await bot.send("[RoverSign] [全部签到] 已开始执行!")
    msg = await rover_auto_sign_task()
    await bot.send("[RoverSign] [全部签到] 执行完成!")
    await bot.send(msg)


@waves_sign_all.on_regex(("^(订阅|取消订阅)签到结果$"))
async def rover_sign_result(bot: Bot, ev: Event):
    if "取消" in ev.raw_text:
        option = "关闭"
    else:
        option = "开启"

    if option == "关闭":
        await gs_subscribe.delete_subscribe(
            "single", BoardcastTypeEnum.SIGN_RESULT, ev
        )
    else:
        await gs_subscribe.add_subscribe(
            "single", BoardcastTypeEnum.SIGN_RESULT, ev
        )

    await bot.send(f"[RoverSign] [订阅签到结果] 已{option}订阅!")
