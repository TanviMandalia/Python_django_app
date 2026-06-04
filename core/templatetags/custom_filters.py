from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()

@register.filter
def smart_date(value):

    today = timezone.localtime().date()

    if value.date() == today:
        return "Today, " + value.strftime("%I:%M %p")

    elif value.date() == today - timedelta(days=1):
        return "Yesterday, " + value.strftime("%I:%M %p")

    return value.strftime("%d %b, %I:%M %p")