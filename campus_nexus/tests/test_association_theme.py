import hashlib
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings

from campus_nexus.models import Association


class AssociationThemeGenerationTests(TestCase):
    def test_logo_change_replaces_theme_with_cache_busted_filename(self):
        first_css = "body { color: green; }"
        second_css = "body { color: purple; }"

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                with patch("campus_nexus.models.get_association_theme", side_effect=[first_css, second_css]):
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
                    first_hash = hashlib.sha256(first_css.encode("utf-8")).hexdigest()[:12]
                    self.assertEqual(first_theme_name, f"associations/themes/association_{association.id}_{first_hash}.css")
                    self.assertTrue(default_storage.exists(first_theme_name))

                    association.logo_image = SimpleUploadedFile(
                        "logo-b.png",
                        b"second-logo",
                        content_type="image/png",
                    )
                    association.save()
                    association.refresh_from_db()

                    second_theme_name = association.theme_css_file.name
                    second_hash = hashlib.sha256(second_css.encode("utf-8")).hexdigest()[:12]
                    self.assertEqual(second_theme_name, f"associations/themes/association_{association.id}_{second_hash}.css")
                    self.assertNotEqual(second_theme_name, first_theme_name)
                    self.assertFalse(default_storage.exists(first_theme_name))
                    self.assertTrue(default_storage.exists(second_theme_name))

                    with default_storage.open(second_theme_name, "rb") as theme_file:
                        self.assertEqual(theme_file.read().decode("utf-8"), second_css)
