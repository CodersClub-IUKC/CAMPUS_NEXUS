from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class Phase12DeploymentHardeningTests(SimpleTestCase):
    def test_health_endpoint_is_public_and_minimal(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @override_settings(GITHUB_DEPLOY_WEBHOOK_ENABLED=False)
    def test_github_deploy_webhook_is_disabled_by_default(self):
        response = self.client.post("/api/v2/campus_nexus/deploy/", data=b"{}", content_type="application/json")

        self.assertEqual(response.status_code, 403)
        self.assertIn("disabled", response.content.decode("utf-8").lower())
