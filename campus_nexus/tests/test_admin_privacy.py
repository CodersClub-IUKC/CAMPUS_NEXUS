from django.test import TestCase
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.urls import reverse

from campus_nexus.models import Faculty, Association, Member, Membership


class AdminPrivacyIntegrationTests(TestCase):
    """
    Integration-style tests for admin privacy and membership workflow.

    These tests focus on:
    - Association admin must not browse Members list
    - Association admin can still search Members via autocomplete when creating Membership
    - Guild/Dean can access full Members list
    - Association admin must not see other associations' memberships/fees/totals (Step 4 tests later)
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        # --- Core org structure ---
        cls.faculty = Faculty.objects.create(name="Faculty of Science")

        cls.assoc_a = Association.objects.create(
            name="Association A",
            faculty=cls.faculty,
            description="A",
        )
        cls.assoc_b = Association.objects.create(
            name="Association B",
            faculty=cls.faculty,
            description="B",
        )

        # --- Users ---
        cls.superuser = User.objects.create_superuser(
            username="super",
            email="super@example.com",
            password="pass12345",
        )

        cls.guild_admin = User.objects.create_user(
            username="guild",
            email="guild@example.com",
            password="pass12345",
            is_staff=True,
        )
        cls.dean = User.objects.create_user(
            username="dean",
            email="dean@example.com",
            password="pass12345",
            is_staff=True,
        )

        cls.assoc_admin_a = User.objects.create_user(
            username="assocA",
            email="assocA@example.com",
            password="pass12345",
            is_staff=True,
        )
        cls.assoc_admin_b = User.objects.create_user(
            username="assocB",
            email="assocB@example.com",
            password="pass12345",
            is_staff=True,
        )


        from campus_nexus.models import Guild, Dean, AssociationAdmin

        cls.guild_profile = Guild.objects.create(user=cls.guild_admin)
        cls.dean_profile = Dean.objects.create(user=cls.dean)

        cls.assoc_admin_profile_a = AssociationAdmin.objects.create(
            user=cls.assoc_admin_a,
            association=cls.assoc_a,
        )
        cls.assoc_admin_profile_b = AssociationAdmin.objects.create(
            user=cls.assoc_admin_b,
            association=cls.assoc_b,
        )


        # --- Members ---
        cls.member_1 = Member.objects.create(
            first_name="Ibrahim",
            last_name="Sabavuma",
            email="ibrahim@example.com",
            phone="0700000001",
            registration_number="223-063012-002",
            national_id_number="CM12345678AA",
            member_type="student",
            faculty=cls.faculty,
        )
        cls.member_2 = Member.objects.create(
            first_name="Zakia",
            last_name="Ali",
            email="zakia@example.com",
            phone="0700000002",
            registration_number="223-063012-001",
            national_id_number="CM87654321BB",
            member_type="student",
            faculty=cls.faculty,
        )

        # --- Membership (assoc A has member_1) ---
        cls.membership_a1 = Membership.objects.create(
            association=cls.assoc_a,
            member=cls.member_1,
            status="active",
        )

    def test_assoc_admin_cannot_open_members_changelist(self):
        """
        Assoc admin must not browse /admin/.../member/ list page.
        """
        self.client.login(username="assocA", password="pass12345")
        url = reverse("admin:campus_nexus_member_changelist")
        resp = self.client.get(url)
        # could be 403 or redirect to login depending on how permissions are implemented
        self.assertIn(resp.status_code, (302, 403))

    def test_guild_admin_can_open_members_changelist(self):
        self.client.login(username="guild", password="pass12345")
        url = reverse("admin:campus_nexus_member_changelist")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_dean_can_open_members_changelist(self):
        self.client.login(username="dean", password="pass12345")
        url = reverse("admin:campus_nexus_member_changelist")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_assoc_admin_can_open_membership_add_page(self):
        """
        Assoc admin should be able to add membership (this is needed for autocomplete).
        """
        self.client.login(username="assocA", password="pass12345")
        url = reverse("admin:campus_nexus_membership_add")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_assoc_admin_can_use_member_autocomplete_for_membership(self):
        """
        Assoc admin must NOT see members list,
        but must be able to search member by name/email/phone/regno/nin via autocomplete.
        """
        self.client.login(username="assocA", password="pass12345")

        # This is Django admin autocomplete endpoint
        url = reverse("admin:autocomplete")

        # Search by email substring
        resp = self.client.get(
            url,
            {
                "term": "ibrahim@",
                "app_label": "campus_nexus",
                "model_name": "membership",
                "field_name": "member",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        ids = {item.get("id") for item in data.get("results", [])}
        self.assertIn(str(self.member_1.id), ids)


        # Search by regno substring
        resp = self.client.get(
            url,
            {
                "term": "223-063012-001",
                "app_label": "campus_nexus",
                "model_name": "membership",
                "field_name": "member",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(any("223-063012-001" in item.get("text", "") for item in data.get("results", [])))

        # Search by NIN substring
        resp = self.client.get(
            url,
            {
                "term": "CM123",
                "app_label": "campus_nexus",
                "model_name": "membership",
                "field_name": "member",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        ids = {item.get("id") for item in data.get("results", [])}
        self.assertIn(str(self.member_1.id), ids)
