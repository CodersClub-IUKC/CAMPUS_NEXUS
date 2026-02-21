import hashlib
import time
from urllib.parse import urlencode

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.urls import reverse


class AssociationWhiteLabellingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and hasattr(request.user, "association_admin"):
            assoc = request.user.association_admin.association
            app_config = apps.get_app_config("campus_nexus")
            # Change the association verbose name so that all models in the sidebar appear under the association name
            # If more apps are added, this will no longer serve that visual clarity, a more comprehensive approach is required
            # TODO: Devise a proper method of displaying the association name on the admin page that isn't dependent on apps
            app_config.verbose_name = assoc.name
        response = self.get_response(request)
        return response


class AdminLoginRateLimitMiddleware:
    """
    Basic admin login rate limiter:
    - Tracks failed POSTs to /admin/login/
    - Blocks repeated attempts from the same IP+username tuple for a lockout window
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _is_enabled(self):
        return getattr(settings, "ENABLE_ADMIN_LOGIN_RATE_LIMIT", True)

    def _is_admin_login_post(self, request):
        try:
            return request.method == "POST" and request.path == reverse("admin:login")
        except Exception:
            return False

    def _key_suffix(self, request):
        username = (request.POST.get("username") or "").strip().lower()
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        remote_addr = (xff.split(",")[0] if xff else request.META.get("REMOTE_ADDR", "")).strip()
        raw = f"{remote_addr}:{username}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def __call__(self, request):
        if not self._is_enabled() or not self._is_admin_login_post(request):
            return self.get_response(request)

        max_attempts = int(getattr(settings, "ADMIN_LOGIN_MAX_ATTEMPTS", 5))
        lockout_seconds = int(getattr(settings, "ADMIN_LOGIN_LOCKOUT_SECONDS", 900))
        if max_attempts <= 0:
            return self.get_response(request)

        now = int(time.time())
        username = (request.POST.get("username") or "").strip()
        suffix = self._key_suffix(request)
        attempts_key = f"admin_login_attempts:{suffix}"
        lock_key = f"admin_login_locked_until:{suffix}"

        def _lock_redirect(locked_until):
            login_path = reverse("admin:login")
            params = {
                "locked": "1",
                "lockout_until": str(int(locked_until)),
                "username": username,
            }
            next_target = request.POST.get("next") or request.GET.get("next")
            if next_target:
                params["next"] = next_target
            return HttpResponseRedirect(f"{login_path}?{urlencode(params)}")

        locked_until = int(cache.get(lock_key) or 0)
        if locked_until > now:
            return _lock_redirect(locked_until)

        if locked_until:
            cache.delete(lock_key)
            cache.delete(attempts_key)

        response = self.get_response(request)

        login_success = bool(request.user.is_authenticated) and response.status_code in (301, 302)
        if login_success:
            cache.delete(attempts_key)
            cache.delete(lock_key)
            return response

        attempts = int(cache.get(attempts_key) or 0) + 1
        cache.set(attempts_key, attempts, timeout=lockout_seconds)
        if attempts >= max_attempts:
            locked_until = now + lockout_seconds
            cache.set(lock_key, locked_until, timeout=lockout_seconds)
            return _lock_redirect(locked_until)

        return response
