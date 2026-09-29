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


@register.inclusion_tag("includes/media_input.html")
def media_input(name, input_id):
    """The attachment picker outside of a Django form (e.g. the "not OK" dialog)."""
    from tickets.media import ACCEPT

    return {"widget": {"name": name, "attrs": {"id": input_id}}, "accept": ACCEPT}
