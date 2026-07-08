from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from campus_nexus.models import Association, Charge, Fee, Member, Membership, MembershipApplication
from campus_nexus.services.audit import record_audit_event
from campus_nexus.services.charges import get_or_create_charge_for_fee
from campus_nexus.services.membership_eligibility import check_membership_eligibility
from campus_nexus.services.notifications import notify_member_on_commit


@dataclass(frozen=True)
class MembershipApplicationError(Exception):
    code: str
    message: str


def get_required_membership_fee(association: Association) -> Fee:
    fee = (
        Fee.objects.filter(association=association, fee_type="membership")
        .order_by("-created_at")
        .first()
    )
    if not fee:
        raise MembershipApplicationError(
            "membership_fee_not_configured",
            "Membership applications are temporarily unavailable for this association.",
        )
    return fee


def _raise_if_not_eligible(member: Member, association: Association, *, ignored_application_id=None):
    eligibility = check_membership_eligibility(
        member,
        association,
        ignored_application_id=ignored_application_id,
    )
    if not eligibility.is_eligible:
        raise MembershipApplicationError(
            eligibility.code or "membership_not_eligible",
            eligibility.eligibility_reason or "This member is not eligible for this association.",
        )
    return eligibility


def create_membership_application(*, member: Member, association: Association) -> MembershipApplication:
    with transaction.atomic():
        member = Member.objects.select_for_update().get(pk=member.pk)
        association = Association.objects.select_for_update().get(pk=association.pk)
        _raise_if_not_eligible(member, association)

        application = MembershipApplication(
            member=member,
            association=association,
            status=MembershipApplication.STATUS_PENDING_APPROVAL,
        )
        try:
            application.save()
        except IntegrityError as exc:
            raise MembershipApplicationError(
                "application_already_pending",
                "You already have an active application for this association.",
            ) from exc

        record_audit_event(
            actor=None,
            action="MEMBERSHIP_APPLICATION_CREATED",
            obj=application,
            association=association,
            metadata={
                "member_id": str(member.pk),
                "association_id": str(association.pk),
                "status": application.status,
            },
        )
        notify_member_on_commit(
            member_id=member.pk,
            title="Application Submitted",
            message=(
                f"Your application to join {association.name} has been submitted "
                "and is awaiting review."
            ),
            notification_type="application",
            related_url=f"/applications/{application.pk}",
            related_object_type="membership_application",
            related_object_id=application.pk,
            deduplication_key=f"membership_application_{application.pk}_submitted",
        )
        return application


def approve_membership_application(*, application: MembershipApplication, reviewed_by) -> MembershipApplication:
    with transaction.atomic():
        application = (
            MembershipApplication.objects.select_for_update()
            .select_related("member", "association", "membership", "charge")
            .get(pk=application.pk)
        )

        if application.status == MembershipApplication.STATUS_APPROVED_PENDING_PAYMENT:
            return application
        if application.status == MembershipApplication.STATUS_ACTIVE:
            return application
        if application.status != MembershipApplication.STATUS_PENDING_APPROVAL:
            raise MembershipApplicationError(
                "invalid_application_transition",
                "Only pending applications can be approved.",
            )

        member = Member.objects.select_for_update().get(pk=application.member_id)
        association = Association.objects.select_for_update().get(pk=application.association_id)
        _raise_if_not_eligible(member, association, ignored_application_id=application.pk)
        fee = get_required_membership_fee(association)

        membership = application.membership
        if membership is None:
            membership = Membership(
                member=member,
                association=association,
                status="inactive",
            )
            if not membership.subscription_anchor_date:
                membership.subscription_anchor_date = timezone.localdate()
            try:
                membership.full_clean()
                membership.save()
            except (IntegrityError, ValidationError) as exc:
                raise MembershipApplicationError(
                    "membership_creation_failed",
                    "The membership could not be prepared for payment.",
                ) from exc

        charge = application.charge
        if charge is None:
            charge = get_or_create_charge_for_fee(
                membership=membership,
                fee=fee,
                user=reviewed_by,
            )
            record_audit_event(
                actor=reviewed_by,
                action="MEMBERSHIP_FEE_OBLIGATION_CREATED",
                obj=application,
                association=association,
                metadata={
                    "application_id": str(application.pk),
                    "membership_id": str(membership.pk),
                    "charge_id": str(charge.pk),
                    "fee_id": str(fee.pk),
                    "amount_due": str(charge.amount_due),
                },
            )

        old_status = application.status
        application.membership = membership
        application.charge = charge
        application.status = MembershipApplication.STATUS_APPROVED_PENDING_PAYMENT
        application.reviewed_by = reviewed_by
        application.reviewed_at = timezone.now()
        application.rejection_reason = ""
        application.save(
            update_fields=[
                "membership",
                "charge",
                "status",
                "reviewed_by",
                "reviewed_at",
                "rejection_reason",
                "updated_at",
            ]
        )
        record_audit_event(
            actor=reviewed_by,
            action="MEMBERSHIP_APPLICATION_APPROVED",
            obj=application,
            association=association,
            metadata={
                "old_status": old_status,
                "new_status": application.status,
                "member_id": str(member.pk),
                "association_id": str(association.pk),
                "membership_id": str(membership.pk),
                "charge_id": str(charge.pk),
            },
        )
        notify_member_on_commit(
            member_id=member.pk,
            title="Application Approved",
            message=(
                f"Your {association.name} membership application has been approved. "
                "Payment of the required membership fee is now required before activation."
            ),
            notification_type="application",
            related_url=f"/applications/{application.pk}",
            related_object_type="membership_application",
            related_object_id=application.pk,
            deduplication_key=f"membership_application_{application.pk}_approved",
        )
        return activate_membership_if_paid(application=application, actor=reviewed_by)


def reject_membership_application(
    *,
    application: MembershipApplication,
    reviewed_by,
    reason: str,
) -> MembershipApplication:
    reason = (reason or "").strip()
    if not reason:
        raise MembershipApplicationError("rejection_reason_required", "A rejection reason is required.")

    with transaction.atomic():
        application = MembershipApplication.objects.select_for_update().get(pk=application.pk)
        if application.status != MembershipApplication.STATUS_PENDING_APPROVAL:
            raise MembershipApplicationError(
                "invalid_application_transition",
                "Only pending applications can be rejected.",
            )
        old_status = application.status
        application.status = MembershipApplication.STATUS_REJECTED
        application.reviewed_by = reviewed_by
        application.reviewed_at = timezone.now()
        application.rejection_reason = reason
        application.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"])
        record_audit_event(
            actor=reviewed_by,
            action="MEMBERSHIP_APPLICATION_REJECTED",
            obj=application,
            association=application.association,
            metadata={
                "old_status": old_status,
                "new_status": application.status,
                "reason": reason,
            },
        )
        notify_member_on_commit(
            member_id=application.member_id,
            title="Application Not Approved",
            message=f"Your application to join {application.association.name} was not approved. Reason: {reason}",
            notification_type="application",
            related_url=f"/applications/{application.pk}",
            related_object_type="membership_application",
            related_object_id=application.pk,
            deduplication_key=f"membership_application_{application.pk}_rejected",
        )
        return application


def cancel_membership_application(*, application: MembershipApplication, member: Member) -> MembershipApplication:
    with transaction.atomic():
        application = (
            MembershipApplication.objects.select_for_update()
            .select_related("member", "association", "charge")
            .get(pk=application.pk, member=member)
        )
        if application.status == MembershipApplication.STATUS_PENDING_APPROVAL:
            old_status = application.status
            application.status = MembershipApplication.STATUS_CANCELLED
            application.save(update_fields=["status", "updated_at"])
        elif application.status == MembershipApplication.STATUS_APPROVED_PENDING_PAYMENT:
            if application.charge_id and application.charge.payments.exists():
                raise MembershipApplicationError(
                    "application_has_payments",
                    "This application already has payment activity and requires administrative handling.",
                )
            old_status = application.status
            application.status = MembershipApplication.STATUS_CANCELLED
            application.save(update_fields=["status", "updated_at"])
        else:
            raise MembershipApplicationError(
                "invalid_application_transition",
                "This application can no longer be cancelled.",
            )

        record_audit_event(
            actor=None,
            action="MEMBERSHIP_APPLICATION_CANCELLED",
            obj=application,
            association=application.association,
            metadata={"old_status": old_status, "new_status": application.status},
        )
        notify_member_on_commit(
            member_id=application.member_id,
            title="Application Cancelled",
            message=f"Your membership application for {application.association.name} has been cancelled.",
            notification_type="application",
            related_url=f"/applications/{application.pk}",
            related_object_type="membership_application",
            related_object_id=application.pk,
            deduplication_key=f"membership_application_{application.pk}_cancelled",
        )
        return application


def activate_membership_if_paid(*, application: MembershipApplication, actor=None) -> MembershipApplication:
    with transaction.atomic():
        application = (
            MembershipApplication.objects.select_for_update()
            .select_related("member", "association", "membership", "charge")
            .get(pk=application.pk)
        )
        if application.status == MembershipApplication.STATUS_ACTIVE:
            return application
        if application.status != MembershipApplication.STATUS_APPROVED_PENDING_PAYMENT:
            return application
        if not application.membership_id or not application.charge_id:
            return application

        membership = Membership.objects.select_for_update().get(pk=application.membership_id)
        charge = Charge.objects.select_for_update().get(pk=application.charge_id)
        charge.recompute_status()
        if charge.status != "paid" or charge.balance > 0:
            charge.save(update_fields=["status"])
            return application

        if membership.association.faculty_id:
            conflicting = (
                Membership.objects.select_for_update()
                .filter(member=membership.member, association__faculty__isnull=False)
                .exclude(pk=membership.pk)
                .exists()
            )
            if conflicting:
                raise MembershipApplicationError(
                    "academic_membership_limit_reached",
                    "This member already belongs to an academic association.",
                )

        if membership.status != "active":
            membership.status = "active"
            membership.save(update_fields=["status"])

        old_status = application.status
        application.status = MembershipApplication.STATUS_ACTIVE
        application.save(update_fields=["status", "updated_at"])
        charge.save(update_fields=["status"])
        record_audit_event(
            actor=actor,
            action="MEMBERSHIP_ACTIVATED",
            obj=application,
            association=application.association,
            metadata={
                "old_status": old_status,
                "new_status": application.status,
                "membership_id": str(membership.pk),
                "charge_id": str(charge.pk),
            },
        )
        record_audit_event(
            actor=actor,
            action="MEMBERSHIP_PAYMENT_REQUIREMENT_SATISFIED",
            obj=application,
            association=application.association,
            metadata={
                "membership_id": str(membership.pk),
                "charge_id": str(charge.pk),
                "paid_amount": str(charge.amount_paid_total),
            },
        )
        notify_member_on_commit(
            member_id=membership.member_id,
            title="Membership Active",
            message=f"Your {membership.association.name} membership is now active.",
            notification_type="membership",
            related_url=f"/memberships/{membership.pk}",
            related_object_type="membership",
            related_object_id=membership.pk,
            deduplication_key=f"membership_{membership.pk}_activated",
        )
        return application


def activate_membership_if_paid_for_charge(*, charge: Charge, actor=None) -> MembershipApplication | None:
    application = getattr(charge, "membership_application", None)
    if application is None:
        return None
    return activate_membership_if_paid(application=application, actor=actor)


def sync_membership_payment_state_for_charge(*, charge: Charge, actor=None) -> MembershipApplication | None:
    application = getattr(charge, "membership_application", None)
    if application is None:
        return None

    with transaction.atomic():
        application = (
            MembershipApplication.objects.select_for_update()
            .select_related("association", "membership", "charge")
            .get(pk=application.pk)
        )
        if not application.charge_id or application.charge_id != charge.pk:
            return application

        charge = Charge.objects.select_for_update().get(pk=charge.pk)
        old_charge_status = charge.status
        charge.recompute_status()
        if charge.status != old_charge_status:
            charge.save(update_fields=["status"])
            record_audit_event(
                actor=actor,
                action="CHARGE_STATUS_CHANGED",
                obj=charge,
                association=charge.association,
                metadata={
                    "old_status": old_charge_status,
                    "new_status": charge.status,
                    "paid_amount": str(charge.amount_paid_total),
                    "balance": str(charge.balance),
                },
            )

        if application.status == MembershipApplication.STATUS_APPROVED_PENDING_PAYMENT:
            return activate_membership_if_paid(application=application, actor=actor)

        if application.status != MembershipApplication.STATUS_ACTIVE:
            return application

        if charge.status == "paid" and charge.balance <= 0:
            return application

        membership = None
        if application.membership_id:
            membership = Membership.objects.select_for_update().get(pk=application.membership_id)
            if membership.status == "active":
                membership.status = "inactive"
                membership.save(update_fields=["status"])

        old_status = application.status
        application.status = MembershipApplication.STATUS_APPROVED_PENDING_PAYMENT
        application.save(update_fields=["status", "updated_at"])
        record_audit_event(
            actor=actor,
            action="MEMBERSHIP_PAYMENT_REQUIREMENT_REOPENED",
            obj=application,
            association=application.association,
            metadata={
                "old_status": old_status,
                "new_status": application.status,
                "membership_id": str(membership.pk) if membership else "",
                "charge_id": str(charge.pk),
                "charge_status": charge.status,
                "paid_amount": str(charge.amount_paid_total),
                "balance": str(charge.balance),
            },
        )
        notify_member_on_commit(
            member_id=application.member_id,
            title="Payment Required Again",
            message=(
                f"Your {application.association.name} membership payment requirement has reopened "
                "because a recorded payment was reversed. Please review your outstanding balance."
            ),
            notification_type="membership",
            related_url="/finance",
            related_object_type="membership_application",
            related_object_id=application.pk,
            deduplication_key=f"membership_application_{application.pk}_payment_reopened",
        )
        return application
