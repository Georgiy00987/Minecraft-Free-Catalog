"""
Простой in-memory rate limiter.
Позволяет пользователю выполнять действие не чаще чем раз в RATE_SECONDS секунд.
"""

import time
import logging

log = logging.getLogger(__name__)

RATE_SECONDS = 3.0   # глобальный кулдаун между любыми действиями

# {user_id: last_action_timestamp}
_last_action: dict[int, float] = {}


def is_allowed(user_id: int) -> bool:
    """
    Возвращает True если пользователь может выполнить действие.
    Возвращает False если прошло меньше RATE_SECONDS с последнего действия.
    """
    now  = time.monotonic()
    last = _last_action.get(user_id, 0.0)
    if now - last < RATE_SECONDS:
        return False
    _last_action[user_id] = now
    return True


def remaining(user_id: int) -> float:
    """Сколько секунд осталось до следующего разрешённого действия."""
    now  = time.monotonic()
    last = _last_action.get(user_id, 0.0)
    return max(0.0, RATE_SECONDS - (now - last))


def reset(user_id: int):
    """Сбрасывает кулдаун для пользователя (например после /start)."""
    _last_action.pop(user_id, None)
