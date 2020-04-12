"""
Custom tags and filters for inventory

"""
from datetime import datetime

from django.template import Context
from django.template.library import Library
from django.utils.timezone import localtime, now

from ..common import since


register = Library()


@register.simple_tag(takes_context=True)
def format_time(context: Context, dt: datetime) -> str:
    if not dt:
        return ""
    request = context["request"]
    if not hasattr(request, "now"):
        request.now = now()
    formatted = localtime(dt).strftime("%-d %B %Y %H:%M")
    since_then = since(dt, request.now)
    return f"{formatted} ({since_then})"


@register.simple_tag(takes_context=True)
def time_since(context: Context, dt: datetime) -> str:
    if not dt:
        return ""
    request = context["request"]
    if not hasattr(request, "now"):
        request.now = now()
    return since(dt, request.now)
