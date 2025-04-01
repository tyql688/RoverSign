from PIL import Image

from gsuid_core.bot import Bot
from gsuid_core.help.utils import register_help
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..roversign_config import PREFIX
from .get_help import ICON, get_help

sv_rover_help = SV("RoverSign帮助")


@sv_rover_help.on_fullmatch("帮助")
async def send_help_img(bot: Bot, ev: Event):
    await bot.send(await get_help(ev.user_pm))


register_help("RoverSignUID", f"{PREFIX}帮助", Image.open(ICON))
