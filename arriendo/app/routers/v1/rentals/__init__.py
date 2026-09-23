from app.redis import ACTIVATE_REDIS

if ACTIVATE_REDIS:
    from .rentals_with_redis import router
else:
    from .rentals_without_redis import router

__all__ = ["router"]