"""Small presentation helpers shared by multiple services."""

from datetime import datetime, timezone

_DECISION_LABELS = {'allow': 'Allowed', 'deny': 'Denied'}


def relative_time(iso_ts: str) -> str:
    then = datetime.fromisoformat(iso_ts)
    delta = datetime.now(timezone.utc) - then
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return 'just now'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes} min ago'
    hours = minutes // 60
    if hours < 24:
        return f'{hours} hr ago'
    days = hours // 24
    return f'{days} day ago'


def clock_time(iso_ts: str) -> str:
    return datetime.fromisoformat(iso_ts).strftime('%H:%M')


def decision_label(decision: str) -> str:
    return _DECISION_LABELS[decision]
