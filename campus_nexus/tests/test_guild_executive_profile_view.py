from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from campus_nexus.models import (
    Association,
    AssociationAdmin,
    Faculty,
    Guild,
    GuildCabinet,
    GuildExecutive,
    Member,
)


class GuildExecutiveProfileViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()

        cls.faculty = Faculty.objects.create(name="Faculty of Science")
        cls.association = Association.objects.create(name="Association A", faculty=cls.faculty)

        cls.guild_user = user_model.objects.create_user(
            username="guildadmin",
            email="guildadmin@example.com",
            password="pass12345",
            is_staff=True,
        )
        cls.assoc_user = user_model.objects.create_user(
            username="assocadmin",
            email="assocadmin@example.com",
            password="pass12345",
            is_staff=True,
        )

        Guild.objects.create(user=cls.guild_user)
        AssociationAdmin.objects.create(user=cls.assoc_user, association=cls.association)

        cls.member = Member.objects.create(
            first_name="Ibrahim",
            last_name="Sabavuma",
            email="ibrahim@example.com",
            phone="+256700000001",
            registration_number="223-063012-002",
            national_id_number="CM12345678AA",
            member_type="student",
            faculty=cls.faculty,
            nationality="Uganda",
            photo=SimpleUploadedFile("member.jpg", b"fake-image-bytes", content_type="image/jpeg"),
        )

        cls.cabinet = GuildCabinet.objects.create(name="Guild Cabinet", year="2026/2027", is_active=True)
        cls.executive = GuildExecutive.objects.create(
            cabinet=cls.cabinet,
            member=cls.member,
            position_type="minister",
            ministry="Finance",
        )

    def test_association_admin_can_view_guild_executive_profile_card(self):
        self.client.login(username="assocadmin", password="pass12345")
        url = reverse("admin:campus_nexus_guildexecutive_change", args=[self.executive.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "executive-profile-card")
        self.assertContains(response, self.member.full_name)

    def test_association_admin_cannot_edit_guild_executive(self):
        self.client.login(username="assocadmin", password="pass12345")
        url = reverse("admin:campus_nexus_guildexecutive_change", args=[self.executive.id])
        response = self.client.post(
            url,
            {
                "cabinet": self.cabinet.id,
                "position_type": "minister",
                "ministry": "Education",
                "member": self.member.id,
                "reports_to": "",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_guild_admin_can_edit_guild_executive(self):
        self.client.login(username="guildadmin", password="pass12345")
        url = reverse("admin:campus_nexus_guildexecutive_change", args=[self.executive.id])
        response = self.client.post(
            url,
            {
                "cabinet": self.cabinet.id,
                "position_type": "minister",
                "ministry": "Education",
                "member": self.member.id,
                "reports_to": "",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.executive.refresh_from_db()
        self.assertEqual(self.executive.ministry, "Education")

    def test_member_admin_form_exposes_photo_and_country_dropdown(self):
        self.client.login(username="guildadmin", password="pass12345")
        url = reverse("admin:campus_nexus_member_add")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="photo"')
        self.assertContains(response, 'name="nationality"')
        self.assertContains(response, "<option value=\"Uganda\">Uganda</option>", html=False)

