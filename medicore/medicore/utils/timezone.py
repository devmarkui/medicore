from __future__ import annotations

from datetime import datetime, date
from zoneinfo import ZoneInfo

_COLOMBO_TZ = ZoneInfo("Asia/Colombo")


def get_colombo_time() -> datetime:
    return datetime.now(_COLOMBO_TZ)


def get_colombo_date() -> date:
    return get_colombo_time().date()
