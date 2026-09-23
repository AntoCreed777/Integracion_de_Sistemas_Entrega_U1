from app.redis import ACTIVATE_REDIS

if ACTIVATE_REDIS:
    print("Using Redis for caching rentals.")
    from .rentals_with_redis import router
else:
    print("Without Redis for caching rentals.")
    from .rentals_without_redis import router

__all__ = ["router"]