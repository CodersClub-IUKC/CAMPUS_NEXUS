from __future__ import annotations

from campus_nexus.models import Member, MemberNotificationPreference


PREFERENCE_EVENTS = "events"
PREFERENCE_ANNOUNCEMENTS = "announcements"

SUPPORTED_OPTIONAL_PREFERENCES = {
    PREFERENCE_EVENTS: "event_notifications",
    PREFERENCE_ANNOUNCEMENTS: "announcement_notifications",
}


def get_or_create_member_notification_preferences(member: Member) -> MemberNotificationPreference:
    preferences, _created = MemberNotificationPreference.objects.get_or_create(member=member)
    return preferences


def get_member_notification_preferences(member: Member) -> MemberNotificationPreference:
    return get_or_create_member_notification_preferences(member)


def is_optional_notification_enabled(member: Member, preference_key: str | None) -> bool:
    if preference_key is None:
        return True
    field_name = SUPPORTED_OPTIONAL_PREFERENCES.get(preference_key)
    if field_name is None:
        return True

    preferences = getattr(member, "notification_preferences", None)
    if preferences is None:
        preferences = MemberNotificationPreference.objects.filter(member=member).first()
    if preferences is None:
        return True
    return bool(getattr(preferences, field_name))


def update_member_notification_preferences(member: Member, validated_data: dict) -> tuple[MemberNotificationPreference, dict]:
    preferences = get_or_create_member_notification_preferences(member)
    changes = {}
    for field_name, new_value in validated_data.items():
        old_value = getattr(preferences, field_name)
        if old_value != new_value:
            changes[field_name] = {"old": old_value, "new": new_value}
            setattr(preferences, field_name, new_value)
    if changes:
        preferences.save(update_fields=[*changes.keys(), "updated_at"])
    return preferences, changes
