import hashlib
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.test import RequestFactory, TestCase, override_settings

from campus_nexus.models import Association, AssociationAdmin
from campus_nexus.templatetags.association_tags import association_css_url


class AssociationThemeGenerationTests(TestCase):
    def test_logo_change_replaces_theme_with_cache_busted_filename(self):
        first_theme = {
            "primary_color": "#008000",
            "secondary_color": "#00aa00",
            "css": ":root { --bs-primary: #008000; --bs-info: #00aa00; }\n",
        }
        second_theme = {
            "primary_color": "#800080",
            "secondary_color": "#aa00aa",
            "css": ":root { --bs-primary: #800080; --bs-info: #aa00aa; }\n",
        }

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                with patch("campus_nexus.models.get_association_theme_data", side_effect=[first_theme, second_theme]):
                    association = Association.objects.create(
                        name="Science Association",
                        logo_image=SimpleUploadedFile(
                            "logo-a.png",
                            b"first-logo",
                            content_type="image/png",
                        ),
                    )
                    association.refresh_from_db()

                    first_theme_name = association.theme_css_file.name
                    first_hash = hashlib.sha256(first_theme["css"].encode("utf-8")).hexdigest()[:12]
                    self.assertEqual(first_theme_name, f"associations/themes/association_{association.id}_{first_hash}.css")
                    self.assertEqual(association.theme_primary_color, "#008000")
                    self.assertEqual(association.theme_secondary_color, "#00aa00")
                    self.assertEqual(association.theme_version, first_hash)
                    self.assertTrue(default_storage.exists(first_theme_name))

                    association.logo_image = SimpleUploadedFile(
                        "logo-b.png",
                        b"second-logo",
                        content_type="image/png",
                    )
                    association.save()
                    association.refresh_from_db()

                    second_theme_name = association.theme_css_file.name
                    second_hash = hashlib.sha256(second_theme["css"].encode("utf-8")).hexdigest()[:12]
                    self.assertEqual(second_theme_name, f"associations/themes/association_{association.id}_{second_hash}.css")
                    self.assertNotEqual(second_theme_name, first_theme_name)
                    self.assertEqual(association.theme_primary_color, "#800080")
                    self.assertEqual(association.theme_secondary_color, "#aa00aa")
                    self.assertEqual(association.theme_version, second_hash)
                    self.assertFalse(default_storage.exists(first_theme_name))
                    self.assertTrue(default_storage.exists(second_theme_name))

                    with default_storage.open(second_theme_name, "rb") as theme_file:
                        self.assertEqual(theme_file.read().decode("utf-8"), second_theme["css"])

    def test_logo_change_does_not_modify_shared_admin_custom_css(self):
        admin_custom_css = settings.BASE_DIR / "campus_nexus/static/css/admin_custom.css"
        original_content = admin_custom_css.read_text(encoding="utf-8")

        theme = {
            "primary_color": "#123456",
            "secondary_color": "#abcdef",
            "css": ":root { --bs-primary: #123456; --bs-info: #abcdef; }\n",
        }

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                with patch("campus_nexus.models.get_association_theme_data", return_value=theme):
                    association = Association.objects.create(
                        name="Immutable CSS Association",
                        logo_image=SimpleUploadedFile(
                            "logo-a.png",
                            b"first-logo",
                            content_type="image/png",
                        ),
                    )
                    association.logo_image = SimpleUploadedFile(
                        "logo-b.png",
                        b"second-logo",
                        content_type="image/png",
                    )
                    association.save()

        self.assertEqual(admin_custom_css.read_text(encoding="utf-8"), original_content)

    def test_different_association_admins_receive_different_theme_variables(self):
        User = get_user_model()
        request_factory = RequestFactory()
        themes = [
            {
                "primary_color": "#111111",
                "secondary_color": "#222222",
                "css": ":root { --bs-primary: #111111; --bs-info: #222222; }\n",
            },
            {
                "primary_color": "#333333",
                "secondary_color": "#444444",
                "css": ":root { --bs-primary: #333333; --bs-info: #444444; }\n",
            },
        ]

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL="/media/"):
                with patch("campus_nexus.models.get_association_theme_data", side_effect=themes):
                    first_association = Association.objects.create(
                        name="First Association",
                        logo_image=SimpleUploadedFile("first.png", b"first", content_type="image/png"),
                    )
                    second_association = Association.objects.create(
                        name="Second Association",
                        logo_image=SimpleUploadedFile("second.png", b"second", content_type="image/png"),
                    )

                first_user = User.objects.create_user(username="first-admin", password="pass", is_staff=True)
                second_user = User.objects.create_user(username="second-admin", password="pass", is_staff=True)
                AssociationAdmin.objects.create(user=first_user, association=first_association)
                AssociationAdmin.objects.create(user=second_user, association=second_association)

                first_request = request_factory.get("/admin/")
                first_request.user = first_user
                second_request = request_factory.get("/admin/")
                second_request.user = second_user

                first_url = association_css_url({"request": first_request})
                second_url = association_css_url({"request": second_request})

                self.assertNotEqual(first_url, second_url)

                first_association.refresh_from_db()
                second_association.refresh_from_db()
                with default_storage.open(first_association.theme_css_file.name, "rb") as first_file:
                    first_css = first_file.read().decode("utf-8")
                with default_storage.open(second_association.theme_css_file.name, "rb") as second_file:
                    second_css = second_file.read().decode("utf-8")

                self.assertIn("--bs-primary: #111111", first_css)
                self.assertIn("--bs-primary: #333333", second_css)
                self.assertNotEqual(first_css, second_css)
