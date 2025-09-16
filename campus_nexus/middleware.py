class AssociationWhiteLabellingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_template_response(self, request, response):
        from pprint import pprint
        print("="*100)
        pprint(response.context_data)
        print("="*100)
        if assoc_admin := getattr(request.user, "association_admin", None):
            association = assoc_admin.association
            assoc_context = {
                "site_title": f"{association.name.title()} Administration",
                "site_header": f"{association.name.title()} Admin"
            }
            response.context_data = response.context_data | assoc_context
        return response