import redis
import os

ACTIVATE_REDIS: bool = os.getenv("ACTIVATE_REDIS", "False").lower() == "true"

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=6379,
    decode_responses=True,
)