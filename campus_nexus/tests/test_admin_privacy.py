from django.test import TestCase
from django.contrib.admin.sites import AdminSite
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import RequestFactory

from campus_nexus.models import Faculty, Association, Member, Membership, Cabinet, CabinetMember, GuildCabinet


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

    def test_assoc_admin_gets_clear_message_for_duplicate_membership(self):
        self.client.login(username="assocA", password="pass12345")
        url = reverse("admin:campus_nexus_membership_add")
        resp = self.client.post(
            url,
            {
                "member": self.member_1.id,
                "subscription_anchor_date": "",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "already registered in this association")

    def test_assoc_admin_gets_clear_message_for_cross_faculty_member(self):
        other_faculty = Faculty.objects.create(name="Faculty of Business")
        other_assoc = Association.objects.create(
            name="Association C",
            faculty=other_faculty,
            description="C",
        )
        other_member = Member.objects.create(
            first_name="Aisha",
            last_name="K.",
            email="aisha@example.com",
            phone="0700000100",
            registration_number="223-063012-099",
            national_id_number="CM99999999ZZ",
            member_type="student",
            faculty=other_faculty,
        )
        Membership.objects.create(
            association=other_assoc,
            member=other_member,
            status="active",
        )

        self.client.login(username="assocA", password="pass12345")
        url = reverse("admin:campus_nexus_membership_add")
        resp = self.client.post(
            url,
            {
                "member": other_member.id,
                "subscription_anchor_date": "",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "belongs to another faculty-based group")

    def test_assoc_admin_can_open_expense_changelist(self):
        self.client.login(username="assocA", password="pass12345")
        url = reverse("admin:campus_nexus_expense_changelist")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_guild_admin_cannot_open_expense_changelist(self):
        self.client.login(username="guild", password="pass12345")
        url = reverse("admin:campus_nexus_expense_changelist")
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (302, 403))

    def test_dean_cannot_open_expense_changelist(self):
        self.client.login(username="dean", password="pass12345")
        url = reverse("admin:campus_nexus_expense_changelist")
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (302, 403))

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

    def test_assoc_admin_can_use_member_autocomplete_for_cabinet_member(self):
        self.client.login(username="assocA", password="pass12345")

        Cabinet.objects.create(association=self.assoc_a, year="2026/2027")

        url = reverse("admin:autocomplete")
        resp = self.client.get(
            url,
            {
                "term": "ibrahim",
                "app_label": "campus_nexus",
                "model_name": "cabinetmember",
                "field_name": "member",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        ids = {item.get("id") for item in data.get("results", [])}
        self.assertIn(str(self.member_1.id), ids)
        self.assertNotIn(str(self.member_2.id), ids)

    def test_association_changelist_shows_cabinet_president_name(self):
        cabinet = Cabinet.objects.create(association=self.assoc_a, year="2026/2027")
        CabinetMember.objects.create(
            cabinet=cabinet,
            member=self.member_1,
            role="president",
        )

        self.client.login(username="guild", password="pass12345")
        url = reverse("admin:campus_nexus_association_changelist")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.member_1.full_name)

    def test_assoc_admin_on_own_association_sees_membership_fee_and_system_tabs(self):
        self.client.login(username="assocA", password="pass12345")
        url = reverse("admin:campus_nexus_association_change", args=[self.assoc_a.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "memberships-tab")
        self.assertContains(resp, "fees-tab")
        self.assertContains(resp, "system-tab")

    def test_assoc_admin_on_other_association_hides_membership_fee_and_system_tabs(self):
        self.client.login(username="assocA", password="pass12345")
        url = reverse("admin:campus_nexus_association_change", args=[self.assoc_b.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "memberships-tab")
        self.assertNotContains(resp, "fees-tab")
        self.assertNotContains(resp, "system-tab")
        self.assertNotContains(resp, "Total Members")

    def test_assoc_admin_admin_app_list_hides_member_and_includes_expected_modules(self):
        request = RequestFactory().get("/admin/")
        request.user = self.assoc_admin_a

        app_list = admin.site.get_app_list(request)
        campus_app = next(a for a in app_list if a["app_label"] == "campus_nexus")

        model_names = {m["object_name"].lower() for m in campus_app["models"]}
        self.assertNotIn("member", model_names)
        self.assertIn("faculty", model_names)
        self.assertIn("course", model_names)
        self.assertIn("membership", model_names)
        self.assertIn("cabinet", model_names)
        self.assertIn("cabinetmember", model_names)
        self.assertIn("fee", model_names)
        self.assertIn("expense", model_names)
        self.assertIn("guildcabinet", model_names)

    def test_guild_admin_admin_app_list_hides_audit_log(self):
        request = RequestFactory().get("/admin/")
        request.user = self.guild_admin

        app_list = admin.site.get_app_list(request)
        campus_app = next(a for a in app_list if a["app_label"] == "campus_nexus")
        model_names = {m["object_name"].lower() for m in campus_app["models"]}

        self.assertNotIn("auditlog", model_names)
        self.assertNotIn("expense", model_names)

    def test_dean_admin_app_list_hides_expense(self):
        request = RequestFactory().get("/admin/")
        request.user = self.dean

        app_list = admin.site.get_app_list(request)
        campus_app = next(a for a in app_list if a["app_label"] == "campus_nexus")
        model_names = {m["object_name"].lower() for m in campus_app["models"]}

        self.assertNotIn("expense", model_names)

    def test_guild_cabinet_admin_columns_order(self):
        guild_cabinet_admin = admin.site._registry[GuildCabinet]
        self.assertEqual(guild_cabinet_admin.list_display, ("name", "year", "is_active"))
