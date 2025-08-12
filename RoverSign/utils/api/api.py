GAME_ID = 3
SERVER_ID = "76402e5b20be2c39f095a152090afddc"
SERVER_ID_NET = "919752ae5ea09c1ced910dd668a63ffb"


def get_main_url():
    from ...roversign_config.roversign_config import RoverSignConfig

    KuroUrlProxyUrl = RoverSignConfig.get_config("KuroUrlProxyUrl").data
    return KuroUrlProxyUrl or "https://api.kurobbs.com"


MAIN_URL = get_main_url()

# 刷新数据
REFRESH_URL = f"{MAIN_URL}/aki/roleBox/akiBox/refreshData"

# bbs api
GET_GOLD_URL = f"{MAIN_URL}/encourage/gold/getTotalGold"
GET_TASK_URL = f"{MAIN_URL}/encourage/level/getTaskProcess"
FORUM_LIST_URL = f"{MAIN_URL}/forum/list"
LIKE_URL = f"{MAIN_URL}/forum/like"
SIGN_IN_URL = f"{MAIN_URL}/user/signIn"
POST_DETAIL_URL = f"{MAIN_URL}/forum/getPostDetail"
SHARE_URL = f"{MAIN_URL}/encourage/level/shareTask"


# sign
SIGNIN_URL = f"{MAIN_URL}/encourage/signIn/v2"
SIGNIN_TASK_LIST_URL = f"{MAIN_URL}/encourage/signIn/initSignInV2"

# game
MR_REFRESH_URL = f"{MAIN_URL}/gamer/widget/game3/refresh"
LOGIN_LOG_URL = f"{MAIN_URL}/user/login/log"

REQUEST_TOKEN = f"{MAIN_URL}/aki/roleBox/requestToken"


def get_local_proxy_url():
    from ...roversign_config.roversign_config import RoverSignConfig

    LocalProxyUrl = RoverSignConfig.get_config("LocalProxyUrl").data
    if LocalProxyUrl:
        return LocalProxyUrl
    return None
