import redis
import os

ACTIVATE_REDIS: bool = os.getenv("ACTIVATE_REDIS", "False").lower() == "true"

if ACTIVATE_REDIS:
    print("-"*20)
    print("Redis is activated")
    print("-"*20)

    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=6379,
        decode_responses=True,
    )
else:
    print("-"*20)
    print("Redis is not activated")
    print("-"*20)

    redis_client = None