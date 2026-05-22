from __future__ import annotations

from datetime import date

from .config import Frequency


def is_due(frequency: Frequency, today: date) -> bool:
    weekday = today.weekday()  # Mon=0 .. Sun=6
    match frequency:
        case "daily":
            return True
        case "weekly":
            return weekday == 0  # Monday
        case "weekdays":
            return weekday <= 4
        case "weekends":
            return weekday >= 5
    return False
