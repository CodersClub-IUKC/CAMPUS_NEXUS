def jazzmin_dynamic_branding(request):
    if request.user.is_authenticated and hasattr(request.user, "association_admin"):
        assoc = request.user.association_admin.association
        return {
            "site_title": assoc.name,
            "site_header": assoc.name,
            "site_brand": assoc.name,
        }
    return {}
