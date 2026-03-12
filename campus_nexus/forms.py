from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, _unicode_ci_compare


class StaffPasswordResetForm(PasswordResetForm):
    """
    Restrict admin password reset emails to active staff users.
    """

    def get_users(self, email):
        user_model = get_user_model()
        email_field_name = user_model.get_email_field_name()
        users = user_model._default_manager.filter(
            **{
                f"{email_field_name}__iexact": email,
                "is_active": True,
                "is_staff": True,
            }
        )
        return (
            user
            for user in users
            if user.has_usable_password()
            and _unicode_ci_compare(email, getattr(user, email_field_name))
        )
