from django.apps import apps


class AssociationWhiteLabellingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and hasattr(request.user, "association_admin"):
            assoc = request.user.association_admin.association
            app_config = apps.get_app_config("campus_nexus")
            # Change the association verbose name so that all models in the sidebar appear under the association name
            # If more apps are added, this will no longer serve that visual clarity, a more comprehensive approach is required
            # TODO: Devise a proper method of displaying the association name on the admin page that isn't dependent on apps
            app_config.verbose_name = assoc.name
        response = self.get_response(request)
        return response
