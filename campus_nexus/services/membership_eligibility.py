from __future__ import annotations

from dataclasses import dataclass

from campus_nexus.models import Association, Member, Membership


@dataclass(frozen=True)
class MembershipEligibility:
    membership_category: str
    is_eligible: bool
    eligibility_reason: str | None
    current_membership_status: str | None
    code: str | None = None

    def as_dict(self):
        return {
            "membership_category": self.membership_category,
            "is_eligible": self.is_eligible,
            "eligibility_reason": self.eligibility_reason,
            "current_membership_status": self.current_membership_status,
            "code": self.code,
        }


def association_membership_category(association: Association) -> str:
    return "academic" if association.faculty_id else "non_academic"


def member_academic_faculty_id(member: Member) -> int | None:
    if member.faculty_id:
        return member.faculty_id
    course = getattr(member, "course", None)
    if course and course.faculty_id:
        return course.faculty_id
    return None


def check_membership_eligibility(
    member: Member,
    association: Association,
    *,
    ignored_application_id: int | None = None,
) -> MembershipEligibility:
    from campus_nexus.models import MembershipApplication

    current = (
        Membership.objects.filter(member=member, association=association)
        .only("status")
        .first()
    )
    current_status = current.status if current else None
    category = association_membership_category(association)

    if current_status:
        return MembershipEligibility(
            membership_category=category,
            is_eligible=False,
            eligibility_reason="You already have a membership record for this association.",
            current_membership_status=current_status,
            code="membership_already_exists",
        )

    open_applications = MembershipApplication.objects.filter(
        member=member,
        status__in=MembershipApplication.OPEN_STATUSES,
    )
    if ignored_application_id:
        open_applications = open_applications.exclude(pk=ignored_application_id)

    if open_applications.filter(association=association).exists():
        return MembershipEligibility(
            membership_category=category,
            is_eligible=False,
            eligibility_reason="You already have an active application for this association.",
            current_membership_status=None,
            code="application_already_pending",
        )

    if category == "non_academic":
        return MembershipEligibility(
            membership_category=category,
            is_eligible=True,
            eligibility_reason=None,
            current_membership_status=None,
            code=None,
        )

    if member_academic_faculty_id(member) != association.faculty_id:
        return MembershipEligibility(
            membership_category=category,
            is_eligible=False,
            eligibility_reason="Academic association membership is restricted to students of the related faculty.",
            current_membership_status=None,
            code="academic_faculty_mismatch",
        )

    has_other_academic = Membership.objects.filter(
        member=member,
        association__faculty__isnull=False,
    ).exists()
    if has_other_academic:
        return MembershipEligibility(
            membership_category=category,
            is_eligible=False,
            eligibility_reason="You already belong to an academic association.",
            current_membership_status=None,
            code="academic_membership_limit_reached",
        )

    has_open_academic_application = open_applications.filter(association__faculty__isnull=False).exists()
    if has_open_academic_application:
        return MembershipEligibility(
            membership_category=category,
            is_eligible=False,
            eligibility_reason="You already have an active application for an academic association.",
            current_membership_status=None,
            code="academic_application_limit_reached",
        )

    return MembershipEligibility(
        membership_category=category,
        is_eligible=True,
        eligibility_reason=None,
        current_membership_status=None,
        code=None,
    )
