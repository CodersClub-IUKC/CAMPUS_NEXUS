"""
Management command: clear_admin_lockout

Clears the admin login rate-limit lockout for a specific username,
or clears ALL lockout keys from the cache.

Usage:
    python manage.py clear_admin_lockout                  # clear all lockouts
    python manage.py clear_admin_lockout <username>       # clear for one user
"""
import hashlib

from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Clear the admin login rate-limit lockout (superuser locked out fix)."

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            nargs="?",
            default=None,
            help=(
                "Username to unlock. "
                "If omitted, clears the entire cache (removes all lockouts)."
            ),
        )

    def handle(self, *args, **options):
        username = options.get("username")

        if username is None:
            # Nuclear option: wipe the whole cache — only useful when using
            # a dedicated cache (LocMemCache / FileBasedCache just for this app).
            cache.clear()
            self.stdout.write(
                self.style.SUCCESS(
                    "✅  Entire cache cleared. All admin login lockouts have been removed."
                )
            )
            return

        # Try common IP prefixes + the supplied username.
        # We can't reverse the hash, so we brute-force the most likely IPs.
        candidate_ips = [
            "127.0.0.1",
            "::1",
            "localhost",
            "",
        ]
        cleared = 0
        username_lower = username.strip().lower()

        for ip in candidate_ips:
            raw = f"{ip}:{username_lower}"
            suffix = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            attempts_key = f"admin_login_attempts:{suffix}"
            lock_key = f"admin_login_locked_until:{suffix}"

            for key in (attempts_key, lock_key):
                if cache.get(key) is not None:
                    cache.delete(key)
                    cleared += 1

        if cleared:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅  Cleared {cleared} lockout cache key(s) for username '{username}'."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  No lockout cache entries found for username '{username}'. "
                    "They may have already expired, or come from a different IP. "
                    "Run without a username argument to wipe the entire cache."
                )
            )
