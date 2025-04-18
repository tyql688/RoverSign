import random
import string
import time
from datetime import datetime, timedelta
from functools import wraps


def timed_async_cache(expiration, condition=lambda x: True):
    def decorator(func):
        cache = {}

        @wraps(func)
        async def wrapper(*args):
            current_time = time.time()
            # 如果是类方法，args[0]是实例，我们获取类名
            if args and hasattr(args[0], "__class__"):
                cache_key = f"{args[0].__class__.__name__}.{func.__name__}"
            else:
                cache_key = func.__name__

            if cache_key in cache:
                value, timestamp = cache[cache_key]
                if current_time - timestamp < expiration:
                    return value

            value = await func(*args)
            if condition(value):
                cache[cache_key] = (value, current_time)
            return value

        return wrapper

    return decorator


def generate_random_string(length=32):
    # 定义可能的字符集合
    characters = string.ascii_letters + string.digits + string.punctuation
    # 使用random.choice随机选择字符，并连接成字符串
    random_string = "".join(random.choice(characters) for i in range(length))
    return random_string


def get_today_date():
    today = datetime.now()
    return today.strftime("%Y-%m-%d")


def get_yesterday_date():
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def get_two_days_ago_date():
    two_days_ago = datetime.now() - timedelta(days=2)
    return two_days_ago.strftime("%Y-%m-%d")
