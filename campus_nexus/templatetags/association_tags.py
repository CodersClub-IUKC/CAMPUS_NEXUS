from django import template
from django.templatetags.static import static

register = template.Library()

@register.simple_tag(takes_context=True)
def association_css_url(context):
    request = context.get("request")
    if not request or not request.user.is_authenticated:
        return static("css/default.css")

    assoc_admin = getattr(request.user, "association_admin", None)
    assoc = getattr(assoc_admin, "association", None)

    if assoc and getattr(assoc, "theme_css_file", None):
        return assoc.theme_css_file.url

    # fallback for superusers, associations without a logo/theme
    return static("css/default.css")


@register.simple_tag(takes_context=True)
def association_logo_url(context):
    from jazzmin.settings import get_settings
    jazzmin_settings = get_settings()
    default_logo = jazzmin_settings["site_logo"]

    request = context.get("request")
    if not request or not request.user.is_authenticated:
        return default_logo

    assoc_admin = getattr(request.user, "association_admin", None)
    assoc = getattr(assoc_admin, "association", None)

    if assoc and getattr(assoc, "logo_image", None):
        return assoc.logo_image.url

    return default_logo
