from django import template

register = template.Library()

ORIGIN_ICONS = {"client": "🟣", "digitalia": "🔵", "system": "⚙️"}


@register.filter
def origin_icon(value):
    return ORIGIN_ICONS.get(value, "")


@register.simple_tag(takes_context=True)
def sort_url(context, key):
    params = context["request"].GET.copy()
    params["sort"] = key
    params.pop("page", None)
    return "?" + params.urlencode()
