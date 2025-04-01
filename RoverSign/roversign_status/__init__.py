from gsuid_core.status.plugin_status import register_status

from ..utils.database.models import RoverSign, WavesUser
from ..utils.image import get_ICON
from ..utils.util import get_yesterday_date


async def get_sign_num():
    datas = await WavesUser.get_waves_all_user()
    num = 0
    for data in datas:
        if data.sign_switch != "off":
            num += 1
    return num


async def get_today_sign_num():
    datas = await RoverSign.get_all_sign_data_by_date()
    return len(datas)


async def get_yesterday_sign_num():
    yesterday = get_yesterday_date()
    datas = await RoverSign.get_all_sign_data_by_date(date=yesterday)
    return len(datas)


register_status(
    get_ICON(),
    "RoverSign",
    {
        "开启签到": get_sign_num,
        "今日签到": get_today_sign_num,
        "昨日签到": get_yesterday_sign_num,
    },
)
