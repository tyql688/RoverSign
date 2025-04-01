from .models import RoverSign


class SignStatus(int):
    GAME_SIGN = 1  # 游戏签到
    BBS_SIGN = 1  # 社区签到
    BBS_DETAIL = 3  # 社区浏览
    BBS_LIKE = 5  # 社区点赞
    BBS_SHARE = 1  # 社区分享

    @classmethod
    def game_sign_complete(cls, rover_sign: RoverSign):
        return cls.GAME_SIGN == rover_sign.game_sign

    @classmethod
    def bbs_sign_complete(cls, rover_sign: RoverSign):
        return (
            cls.BBS_SIGN == rover_sign.bbs_sign
            and cls.BBS_DETAIL == rover_sign.bbs_detail
            and cls.BBS_LIKE == rover_sign.bbs_like
            and cls.BBS_SHARE == rover_sign.bbs_share
        )
