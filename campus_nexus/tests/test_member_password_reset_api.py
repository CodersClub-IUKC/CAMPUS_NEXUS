import re

from django.contrib.auth import authenticate, get_user_model
from django.contrib.sessions.models import Session
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from campus_nexus.models import AuditLog, Faculty, Member
from campus_nexus.services.member_password_reset import GENERIC_PASSWORD_RESET_DETAIL


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    MEMBER_PORTAL_ORIGIN="https://member.campusnexus.codersug.com",
    PASSWORD_RESET_IDENTIFIER_MAX_REQUESTS_PER_WINDOW=3,
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
        "DEFAULT_THROTTLE_RATES": {
            "password_reset": "100/hour",
            "password_reset_confirm": "100/hour",
        },
    },
)
class MemberPasswordResetApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []
        User = get_user_model()
        self.user = User.objects.create_user(
            username="member.user",
            email="member@example.com",
            password="OldStrongPass123!",
        )
        self.inactive_user = User.objects.create_user(
            username="inactive.member",
            email="inactive@example.com",
            password="OldStrongPass123!",
            is_active=False,
        )
        self.staff_user = User.objects.create_user(
            username="staff.only",
            email="staff@example.com",
            password="OldStrongPass123!",
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            username="root.only",
            email="root@example.com",
            password="OldStrongPass123!",
        )
        self.unlinked_user = User.objects.create_user(
            username="unlinked.member",
            email="unlinked@example.com",
            password="OldStrongPass123!",
        )
        self.faculty = Faculty.objects.create(name="Science")
        self.member = Member.objects.create(
            user=self.user,
            first_name="Safia",
            last_name="Nalukwago",
            email="profile-member@example.com",
            phone="+256700000001",
            registration_number="REG001",
            member_type="student",
            faculty=self.faculty,
        )
        self.inactive_member = Member.objects.create(
            user=self.inactive_user,
            first_name="Inactive",
            last_name="Member",
            email="profile-inactive@example.com",
            phone="+256700000002",
            registration_number="REG002",
            member_type="student",
            faculty=self.faculty,
        )
        self.member_without_user = Member.objects.create(
            first_name="No",
            last_name="User",
            email="profile-no-user@example.com",
            phone="+256700000003",
            registration_number="REG003",
            member_type="student",
            faculty=self.faculty,
        )
        self.request_url = "/api/v1/auth/password-reset/request/"
        self.validate_url = "/api/v1/auth/password-reset/validate/"
        self.confirm_url = "/api/v1/auth/password-reset/confirm/"

    def request_reset(self, identifier):
        return self.client.post(self.request_url, {"identifier": identifier}, format="json")

    def reset_parts_from_email(self):
        body = mail.outbox[-1].body
        match = re.search(r"/reset-password/([^/\s]+)/([^/\s]+)", body)
        self.assertIsNotNone(match)
        return match.group(1), match.group(2)

    def assert_generic_request_response(self, response):
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data, {"detail": GENERIC_PASSWORD_RESET_DETAIL})

    def session_count_for_user(self, user):
        count = 0
        for session in Session.objects.all():
            if str(session.get_decoded().get("_auth_user_id")) == str(user.pk):
                count += 1
        return count

    def test_request_sends_email_for_eligible_member_portal_account(self):
        response = self.request_reset("member.user")

        self.assert_generic_request_response(response)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Campus Nexus Password Recovery")
        self.assertEqual(mail.outbox[0].to, ["member@example.com"])
        self.assertIn("https://member.campusnexus.codersug.com/reset-password/", mail.outbox[0].body)
        self.assertNotIn("OldStrongPass123", mail.outbox[0].body)
        self.assertNotIn("Bearer", mail.outbox[0].body)
        self.assertTrue(mail.outbox[0].alternatives)
        self.assertTrue(
            AuditLog.objects.filter(
                action="MEMBER_PASSWORD_RESET_REQUESTED",
                model_name="campus_nexus.member",
                object_id=str(self.member.pk),
            ).exists()
        )

    def test_request_returns_same_response_without_email_for_ineligible_accounts(self):
        cases = [
            "missing.user",
            "REG003",
            "inactive.member",
            "staff.only",
            "root.only",
            "unlinked.member",
        ]

        for identifier in cases:
            with self.subTest(identifier=identifier):
                response = self.client.post(
                    self.request_url,
                    {"identifier": identifier},
                    format="json",
                    REMOTE_ADDR=f"192.0.2.{cases.index(identifier) + 1}",
                )
                self.assert_generic_request_response(response)

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AuditLog.objects.filter(action="MEMBER_PASSWORD_RESET_REQUESTED").count(), 0)

    def test_malformed_request_validates_normally(self):
        response = self.client.post(self.request_url, {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("identifier", response.data)

    def test_validate_endpoint_returns_boolean_only(self):
        self.request_reset("member.user")
        uid, token = self.reset_parts_from_email()

        valid = self.client.post(self.validate_url, {"uid": uid, "token": token}, format="json")
        invalid = self.client.post(self.validate_url, {"uid": uid, "token": "bad-token"}, format="json")
        tampered = self.client.post(self.validate_url, {"uid": "bad-uid", "token": token}, format="json")

        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.data, {"valid": True})
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(invalid.data, {"valid": False})
        self.assertEqual(tampered.status_code, 200)
        self.assertEqual(tampered.data, {"valid": False})

    def test_confirm_rejects_mismatch_and_weak_password(self):
        self.request_reset("member.user")
        uid, token = self.reset_parts_from_email()

        mismatch = self.client.post(
            self.confirm_url,
            {
                "uid": uid,
                "token": token,
                "new_password": "NewStrongPass123!",
                "new_password_confirm": "DifferentStrongPass123!",
            },
            format="json",
        )
        weak = self.client.post(
            self.confirm_url,
            {
                "uid": uid,
                "token": token,
                "new_password": "123",
                "new_password_confirm": "123",
            },
            format="json",
        )

        self.assertEqual(mismatch.status_code, 400)
        self.assertIn("new_password_confirm", mismatch.data)
        self.assertEqual(weak.status_code, 400)
        self.assertIn("new_password", weak.data)

    def test_confirm_resets_password_once_and_blacklists_refresh_tokens(self):
        refresh = RefreshToken.for_user(self.user)
        self.assertTrue(OutstandingToken.objects.filter(user=self.user).exists())
        self.client.login(username="member.user", password="OldStrongPass123!")
        self.assertEqual(self.session_count_for_user(self.user), 1)
        old_hash = self.user.password

        self.request_reset("member.user")
        uid, token = self.reset_parts_from_email()
        response = self.client.post(
            self.confirm_url,
            {
                "uid": uid,
                "token": token,
                "new_password": "NewStrongPass123!",
                "new_password_confirm": "NewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"detail": "Your password has been reset successfully. You can now sign in."},
        )
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.password, old_hash)
        self.assertIsNone(authenticate(username="member.user", password="OldStrongPass123!"))
        self.assertEqual(authenticate(username="member.user", password="NewStrongPass123!"), self.user)
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists())
        self.assertEqual(self.session_count_for_user(self.user), 0)
        self.assertTrue(AuditLog.objects.filter(action="MEMBER_PASSWORD_RESET_COMPLETED").exists())

        replay = self.client.post(
            self.confirm_url,
            {
                "uid": uid,
                "token": token,
                "new_password": "AnotherStrongPass123!",
                "new_password_confirm": "AnotherStrongPass123!",
            },
            format="json",
        )
        self.assertEqual(replay.status_code, 400)

    def test_audit_logs_do_not_store_reset_token_or_password(self):
        self.request_reset("member.user")
        uid, token = self.reset_parts_from_email()
        self.client.post(
            self.confirm_url,
            {
                "uid": uid,
                "token": token,
                "new_password": "NewStrongPass123!",
                "new_password_confirm": "NewStrongPass123!",
            },
            format="json",
        )

        audit_text = " ".join(str(log.metadata) for log in AuditLog.objects.all())
        self.assertNotIn(token, audit_text)
        self.assertNotIn("NewStrongPass123", audit_text)

    def test_existing_auth_endpoints_still_work(self):
        login = self.client.post(
            "/api/v1/auth/login/",
            {"username": "member.user", "password": "OldStrongPass123!"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        refresh = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh": login.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh.status_code, 200)
        logout_refresh = refresh.data.get("refresh", login.data["refresh"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        me = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me.status_code, 200)
        logout = self.client.post(
            "/api/v1/auth/logout/",
            {"refresh": logout_refresh},
            format="json",
        )
        self.assertEqual(logout.status_code, 204)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    MEMBER_PORTAL_ORIGIN="https://member.campusnexus.codersug.com",
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
        "DEFAULT_THROTTLE_RATES": {
            "password_reset": "2/hour",
            "password_reset_confirm": "100/hour",
        },
    },
)
class MemberPasswordResetThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []

    def test_request_endpoint_is_ip_throttled(self):
        url = "/api/v1/auth/password-reset/request/"

        responses = [
            self.client.post(url, {"identifier": f"missing-{index}"}, format="json")
            for index in range(6)
        ]

        self.assertEqual([response.status_code for response in responses[:5]], [202, 202, 202, 202, 202])
        self.assertEqual(responses[5].status_code, 429)
