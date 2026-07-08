from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from campus_nexus.models import Event, EventRegistration, Member, Membership
from campus_nexus.services.audit import record_audit_event
from campus_nexus.services.notifications import notify_member_on_commit


@dataclass(frozen=True)
class EventRegistrationError(Exception):
    code: str
    message: str


@dataclass(frozen=True)
class EventRegistrationEligibility:
    eligible: bool
    reason: str = ""
    reason_code: str = ""


def check_event_registration_eligibility(member: Member, event: Event) -> EventRegistrationEligibility:
    if event.event_date < timezone.now():
        return EventRegistrationEligibility(
            False,
            "Registration is closed because this event has already started.",
            "event_ended",
        )

    membership = Membership.objects.filter(
        member=member,
        association=event.association,
    ).first()
    if membership is None:
        return EventRegistrationEligibility(
            False,
            f"An active {event.association.name} membership is required to register for this event.",
            "active_membership_required",
        )
    if membership.status == "suspended":
        return EventRegistrationEligibility(
            False,
            "Suspended memberships cannot register for this event.",
            "membership_suspended",
        )
    if membership.status != "active":
        return EventRegistrationEligibility(
            False,
            f"An active {event.association.name} membership is required to register for this event.",
            "active_membership_required",
        )
    return EventRegistrationEligibility(True)


def member_can_register_for_event(member: Member, event: Event) -> bool:
    return check_event_registration_eligibility(member, event).eligible


def get_event_registration(member: Member, event: Event) -> EventRegistration | None:
    return EventRegistration.objects.filter(member=member, event=event).first()


def register_for_event(*, member: Member, event: Event) -> EventRegistration:
    with transaction.atomic():
        event = Event.objects.select_for_update().select_related("association").get(pk=event.pk)
        member = Member.objects.select_for_update().get(pk=member.pk)
        eligibility = check_event_registration_eligibility(member, event)
        if not eligibility.eligible:
            raise EventRegistrationError(
                eligibility.reason_code or "event_registration_not_allowed",
                eligibility.reason or "You are not eligible to register for this event.",
            )

        registration, created = EventRegistration.objects.select_for_update().get_or_create(
            member=member,
            event=event,
            defaults={"status": EventRegistration.STATUS_REGISTERED},
        )
        transitioned = created
        old_status = None if created else registration.status
        if not created and registration.status == EventRegistration.STATUS_CANCELLED:
            registration.status = EventRegistration.STATUS_REGISTERED
            registration.registered_at = timezone.now()
            registration.cancelled_at = None
            registration.transition_version += 1
            registration.save(update_fields=["status", "registered_at", "cancelled_at", "transition_version", "updated_at"])
            transitioned = True

        if transitioned:
            record_audit_event(
                actor=None,
                action="EVENT_REGISTRATION_CREATED" if created else "EVENT_REGISTRATION_RESTORED",
                obj=registration,
                association=event.association,
                metadata={
                    "event_id": str(event.pk),
                    "event_registration_id": str(registration.pk),
                    "member_id": str(member.pk),
                    "old_status": old_status or "",
                    "new_status": registration.status,
                },
            )
            notify_member_on_commit(
                member_id=member.pk,
                title="Event Registration Confirmed",
                message=f"You have registered for {event.title}.",
                notification_type="event",
                related_url=f"/events/{event.pk}",
                related_object_type="event_registration",
                related_object_id=registration.pk,
                deduplication_key=f"event_registration_{registration.pk}_registered_{registration.transition_version}",
            )
        return registration


def cancel_event_registration(*, member: Member, event: Event) -> EventRegistration:
    with transaction.atomic():
        event = Event.objects.select_for_update().select_related("association").get(pk=event.pk)
        registration = (
            EventRegistration.objects.select_for_update()
            .filter(member=member, event=event)
            .first()
        )
        if registration is None:
            raise EventRegistrationError(
                "event_registration_not_found",
                "You are not registered for this event.",
            )
        if event.event_date <= timezone.now():
            raise EventRegistrationError(
                "event_already_started",
                "Registration can no longer be cancelled because this event has already started.",
            )
        transitioned = registration.status != EventRegistration.STATUS_CANCELLED
        if registration.status != EventRegistration.STATUS_CANCELLED:
            old_status = registration.status
            registration.status = EventRegistration.STATUS_CANCELLED
            registration.cancelled_at = timezone.now()
            registration.transition_version += 1
            registration.save(update_fields=["status", "cancelled_at", "transition_version", "updated_at"])

        if transitioned:
            record_audit_event(
                actor=None,
                action="EVENT_REGISTRATION_CANCELLED",
                obj=registration,
                association=event.association,
                metadata={
                    "event_id": str(event.pk),
                    "event_registration_id": str(registration.pk),
                    "member_id": str(member.pk),
                    "old_status": old_status,
                    "new_status": registration.status,
                },
            )
            notify_member_on_commit(
                member_id=member.pk,
                title="Event Registration Cancelled",
                message=f"Your registration for {event.title} has been cancelled.",
                notification_type="event",
                related_url=f"/events/{event.pk}",
                related_object_type="event_registration",
                related_object_id=registration.pk,
                deduplication_key=f"event_registration_{registration.pk}_cancelled_{registration.transition_version}",
            )
        return registration
