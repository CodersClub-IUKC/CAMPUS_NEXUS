from django.test import SimpleTestCase
from django.urls import reverse


class PwaEndpointTests(SimpleTestCase):
    def test_manifest_is_available_with_icons(self):
        response = self.client.get(reverse("webmanifest"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        manifest = response.json()
        self.assertEqual(manifest["name"], "Campus Nexus")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
        self.assertIn(
            {
                "src": "/static/img/pwa-icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            manifest["icons"],
        )
        self.assertIn(
            {
                "src": "/static/img/pwa-icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
            manifest["icons"],
        )

    def test_service_worker_is_root_scoped_javascript(self):
        response = self.client.get(reverse("service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        content = response.content.decode()
        self.assertIn('const CACHE_PREFIX = "campus-nexus-pwa-";', content)
        self.assertIn('"/api/v2/campus_nexus/"', content)
        self.assertIn('request.method !== "GET"', content)

    def test_offline_fallback_is_public_html(self):
        response = self.client.get(reverse("offline"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You are currently offline")
        self.assertContains(response, "CAMPUS_NEXUS.png")

    def test_admin_login_page_exposes_pwa_metadata(self):
        response = self.client.get(reverse("admin:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rel="manifest"')
        self.assertContains(response, reverse("webmanifest"))
        self.assertContains(response, 'navigator.serviceWorker.register("/service-worker.js"')
