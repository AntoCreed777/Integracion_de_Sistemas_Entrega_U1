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



class RentalCache:
    def __init__(self, client: redis.Redis | None):
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def get(self, key: str) -> str | None:
        if self._client is None:
            return None
        return self._client.get(key)

    def set(self, key: str, value: str, ttl_seconds: int = 60) -> None:
        if self._client is not None:
            self._client.setex(key, ttl_seconds, value)

    def invalidate(self, rental_id: int | None = None) -> None:
        if self._client is None:
            return
        if rental_id is not None:
            self._client.delete(f"rental:{rental_id}")
        for key in self._client.scan_iter("rentals:list:*"):
            self._client.delete(key)


_rental_cache = RentalCache(redis_client)


def get_rental_cache() -> RentalCache:
    return _rental_cache