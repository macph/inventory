"""
Custom tags and filters for inventory

"""
from datetime import datetime, date
from typing import Optional

from django.template import Context
from django.template.library import Library
from django.utils.timezone import localtime, now

from ..common import natural, since


register = Library()


@register.simple_tag
def format_time(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return localtime(dt).strftime("%-d %B %Y %H:%M")


@register.simple_tag(takes_context=True)
def time_since(context: Context, dt: Optional[date], truncate: bool = False) -> str:
    if not dt:
        return ""
    request = context["request"]
    if not hasattr(request, "now"):
        request.now = now()
    d = dt if not truncate else date(dt.year, dt.month, dt.day)
    return since(d, request.now)


@register.simple_tag(takes_context=True)
def natural_date(context: Context, dt: Optional[date]) -> str:
    if not dt:
        return ""
    request = context["request"]
    if not hasattr(request, "now"):
        request.now = now()
    local_dt = localtime(dt) if hasattr(dt, "hour") else dt
    return natural(local_dt, localtime(request.now))


@register.simple_tag
def timestamp(dt: Optional[datetime]) -> Optional[int]:
    return int(dt.timestamp() * 1000) if dt else None
