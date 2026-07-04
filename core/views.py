from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import never_cache


PWA_THEME_COLOR = "#0b5ed7"
PWA_CACHE_VERSION = "2026-07-04-v1"


def webmanifest(request):
    manifest = {
        "name": "Campus Nexus",
        "short_name": "Campus Nexus",
        "description": "Campus Nexus administration and association management.",
        "start_url": "/admin/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": PWA_THEME_COLOR,
        "icons": [
            {
                "src": static("img/pwa-icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": static("img/pwa-icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
    }
    response = JsonResponse(manifest)
    response["Content-Type"] = "application/manifest+json"
    response["Cache-Control"] = "public, max-age=3600"
    return response


@never_cache
def service_worker(request):
    response = render(
        request,
        "pwa/service-worker.js",
        {
            "cache_version": PWA_CACHE_VERSION,
            "static_url": settings.STATIC_URL,
        },
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = "/"
    return response


def offline(request):
    response = render(request, "pwa/offline.html")
    response["Cache-Control"] = "public, max-age=3600"
    return response
