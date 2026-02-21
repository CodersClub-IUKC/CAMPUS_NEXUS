from dataclasses import fields
from django.utils import timezone
from urllib import request
from django.conf import settings
from django.contrib import admin, messages
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.core.mail import send_mail
from django.db import transaction
from django.utils.html import format_html
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, resolve
from datetime import timedelta

from campus_nexus.models import *
from .finance_utils import get_or_create_charge_for_fee, create_charge_custom
from .notifications.email_utils import send_payment_recorded_email
from campus_nexus.services.subscriptions import ensure_current_subscription_charge, recompute_overdue_flags_for_association
from campus_nexus.services.subscription_emails import send_subscription_reminder_email
from campus_nexus.services.audit import record_audit_event

# ---------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------
class CheckUserIdentityMixin:
    def is_superuser(self, request):
        return request.user.is_superuser

    def is_association_admin(self, request):
        return getattr(request.user, "association_admin", None)

    def is_guild_admin(self, request):
        return getattr(request.user, "guild", None)

    def is_dean(self, request):
        return getattr(request.user, "dean", None)



# ---------------------------------------------------------------------
# Inlines (MUST be defined before they are referenced)
# ---------------------------------------------------------------------
from django.core.exceptions import PermissionDenied

class AssociationInlineGuardMixin(CheckUserIdentityMixin):
    """
    Inline access rules when shown under AssociationModelAdmin:
    - Guild/superuser: full
    - Dean: view-only
    - Association admin: edit only when viewing own association, otherwise view-only
    """

    def _is_own_association_page(self, request, obj):
        assoc_admin = getattr(request.user, "association_admin", None)
        if not assoc_admin or not obj:
            return False
        return obj.id == assoc_admin.association_id

    def has_add_permission(self, request, obj=None):
        if request.user.is_superuser or self.is_guild_admin(request):
            return True
        if self.is_dean(request):
            return False
        if self.is_association_admin(request):
            return self._is_own_association_page(request, obj)
        return False

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser or self.is_guild_admin(request):
            return True
        if self.is_dean(request):
            return False
        if self.is_association_admin(request):
            return self._is_own_association_page(request, obj)
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser or self.is_guild_admin(request):
            return True
        if self.is_dean(request):
            return False
        if self.is_association_admin(request):
            return self._is_own_association_page(request, obj)
        return False

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj) or ())
        if self.is_dean(request):
            # everything readonly
            return [f.name for f in self.model._meta.fields]
        if self.is_association_admin(request) and not self._is_own_association_page(request, obj):
            return [f.name for f in self.model._meta.fields]
        return ro

class CabinetMemberInline(CheckUserIdentityMixin, admin.TabularInline):
    model = CabinetMember
    extra = 0
    show_change_link = False
    autocomplete_fields = ("member",)

    # Ensures dropdown/autocomplete only shows members who belong to the cabinet's association
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "member" and getattr(request.user, "association_admin", None) and not self.is_guild_admin(request):
            assoc = request.user.association_admin.association
            kwargs["queryset"] = Member.objects.filter(memberships__association=assoc).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class MembershipInline(AssociationInlineGuardMixin, admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("member",)
    show_change_link = False
    fields = ("member", "status", "joined_at")
    readonly_fields = ("joined_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin and self.parent_object and self.parent_object.id != assoc_admin.association_id:
            return qs.none()
        return qs

    def get_formset(self, request, obj=None, **kwargs):
        # store parent object for get_queryset
        self.parent_object = obj
        return super().get_formset(request, obj, **kwargs)

class FeeInline(AssociationInlineGuardMixin, admin.TabularInline):
    model = Fee
    extra = 0
    show_change_link = False
    fields = ("fee_type", "amount", "duration_months", "created_at")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin and self.parent_object and self.parent_object.id != assoc_admin.association_id:
            return qs.none()
        return qs

    def get_formset(self, request, obj=None, **kwargs):
        self.parent_object = obj
        return super().get_formset(request, obj, **kwargs)

class CabinetInline(AssociationInlineGuardMixin, admin.TabularInline):
    model = Cabinet
    extra = 0
    show_change_link = False 
    fields = ("year",)

class GuildExecutiveInline(admin.TabularInline):
    model = GuildExecutive
    extra = 0
    autocomplete_fields = ("member", "reports_to")
    fields = ("group_label", "position_type", "ministry", "member", "reports_to", "photo", "photo_preview")
    readonly_fields = ("group_label", "photo_preview")

    def group_label(self, obj):
        t = getattr(obj, "position_type", "")
        if t in ["guild_president", "lady_vice", "vice_lady_vice", "prime_minister"]:
            return "TOP EXECUTIVE"
        if t == "minister":
            return "MINISTERS"
        if t == "state_minister":
            return "STATE MINISTERS"
        return ""
    group_label.short_description = ""

    def photo_preview(self, obj):
        if obj and obj.photo:
            return format_html(
                '<img src="{}" style="width:34px;height:34px;border-radius:50%;object-fit:cover;" />',
                obj.photo.url
            )
        return "—"
    photo_preview.short_description = ""

class AssociationPresidentInline(admin.StackedInline):
    model = AssociationAdmin
    can_delete = False
    extra = 0
    fields = ("user", "title", "bio", "profile_photo", "photo_preview")
    readonly_fields = ("user", "photo_preview")

    def photo_preview(self, obj):
        if obj and obj.profile_photo:
            return format_html(
                '<img src="{}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;" />',
                obj.profile_photo.url
            )
        return "—"
    photo_preview.short_description = "Preview"

# ---------------------------------------------------------------------
# Role assignment models (superuser only)
# ---------------------------------------------------------------------
@admin.register(Guild)
class GuildAdmin(admin.ModelAdmin):
    list_display = ("user",)
    search_fields = ("user__username", "user__email")
    ordering = ("user__username",)
    raw_id_fields = ("user",)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Dean)
class DeanAdmin(admin.ModelAdmin):
    """
    Dean of Students role assignment.
    Creating a record here grants the selected user the 'Dean' role.
    """
    list_display = ("user",)
    search_fields = ("user__username", "user__email")
    raw_id_fields = ("user",)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
@admin.register(AssociationAdmin)
class AssociationAdminAdmin(admin.ModelAdmin):
    list_display = ("association", "user", "title")
    search_fields = (
        "association__name",
        "user__username",
        "user__first_name",
        "user__last_name",
    )
    fields = ("association", "user", "title", "bio", "profile_photo")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

# ---------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------
@admin.register(Faculty)
class FacultyAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

    def has_module_permission(self, request):
        return (
            request.user.is_superuser
            or self.is_guild_admin(request)
            or self.is_dean(request)
            or self.is_association_admin(request)
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return request.user.is_superuser or self.is_guild_admin(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or self.is_guild_admin(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or self.is_guild_admin(request)

@admin.register(Course)
class CourseAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("name", "faculty")
    list_filter = ("faculty",)
    search_fields = ("name", "faculty__name")

    def has_module_permission(self, request):
        return (
            request.user.is_superuser
            or self.is_guild_admin(request)
            or self.is_dean(request)
            or self.is_association_admin(request)
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return request.user.is_superuser or self.is_guild_admin(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or self.is_guild_admin(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or self.is_guild_admin(request)


@admin.register(Association)
class AssociationModelAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    """
    Association details page:
    - Guild: full edit
    - Dean: view-only
    - Association admin: can edit only branding fields
    """
    list_display = ("name", "faculty","president_name", "created_at", "description")
    search_fields = ("name",)
    list_filter = ("faculty",)
    ordering = ("-created_at",)

    # Association "details screen" additions
    inlines = [AssociationPresidentInline, MembershipInline, FeeInline, CabinetInline]

    BRANDING_FIELDS = ("description", "logo_image")
    
    fieldsets = (
    ("Overview", {
        "fields": ("name", "faculty", "total_members"),
    }),
    ("Branding", {
        "fields": BRANDING_FIELDS,
    }),
    ("System", {
        "fields": ("created_at",),
    }),
)
    
    change_form_template = "admin/campus_nexus/association/change_form.html"

    def _is_own_association_page(self, request, obj):
        assoc_admin = getattr(request.user, "association_admin", None)
        if not assoc_admin or not obj:
            return False
        return obj.id == assoc_admin.association_id
    
    def president_name(self, obj):
        admin_obj = getattr(obj, "associationadmin", None) or getattr(obj, "association_admin", None)
        if admin_obj:
            return admin_obj.user.get_full_name() or admin_obj.user.username
        return "—"
    president_name.short_description = "President"


    def has_module_permission(self, request):
        return (
            request.user.is_superuser
            or self.is_guild_admin(request)
            or self.is_association_admin(request)
            or self.is_dean(request)
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return request.user.is_superuser or self.is_guild_admin(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or self.is_guild_admin(request)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser or self.is_guild_admin(request):
            return True

        # Association admin can "enter change page" for any association,
    
        if self.is_association_admin(request):
            return True

        return False  # dean is view-only
    
    def total_members(self, obj):
        return obj.memberships.count()

    total_members.short_description = "Total Members"
    
    def total_events_posted(self, obj):
        return obj.events.count()
    total_events_posted.short_description = "Total Events Posted"
    
    def total_fees_collected(self, obj):
        """
        Assumes you have Payment model with `amount`
        and it links to Association either directly or via membership.
        Update the queryset path if your Payment relationships differ.
        """
        
        if hasattr(Payment, "association"):
            total = Payment.objects.filter(association=obj).aggregate(s=Sum("amount_paid"))["s"]
        else:
            total = Payment.objects.filter(membership__association=obj).aggregate(s=Sum("amount_paid"))["s"]

        return total or 0
    total_fees_collected.short_description = "Total Fees Collected"

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Everyone with access can view all associations (including association admins)
        if (
            request.user.is_superuser
            or self.is_guild_admin(request)
            or self.is_dean(request)
            or self.is_association_admin(request)
        ):
            return qs

        return qs.none()

    def get_readonly_fields(self, request, obj=None):
        # all DB fields except `id`
        fields = [f.name for f in self.model._meta.fields if f.name != "id"]

        # Always read-only computed stats
        stat_fields = ("total_members", "total_events_posted", "total_fees_collected")
        fields.extend(stat_fields)

        # Dean: fully read-only
        if self.is_dean(request) and not request.user.is_superuser:
            return fields

        # Guild/Superuser: can edit association, but stats remain readonly
        if request.user.is_superuser or self.is_guild_admin(request):
            return ("theme_css_file", "created_at") + stat_fields

        # Association admin: branding-only for OWN association, otherwise fully read-only
        if self.is_association_admin(request):
            assoc = request.user.association_admin.association

            # Viewing another association -> everything read-only
            if obj and obj.id != assoc.id:
                return fields

            # Own association -> only branding fields editable; stats always readonly
            readonly = set(fields) - set(self.BRANDING_FIELDS)
            return tuple(sorted(readonly))

        return fields

    def get_fieldsets(self, request, obj=None):
        # Association admin viewing another association: hide sensitive/system sections.
        if self.is_association_admin(request) and obj and not self._is_own_association_page(request, obj):
            return (
                ("Overview", {"fields": ("name", "faculty")}),
                ("Branding", {"fields": self.BRANDING_FIELDS}),
            )
        return self.fieldsets

    def get_inlines(self, request, obj=None):
        # Association admin viewing another association: hide Memberships and Fees tabs.
        if self.is_association_admin(request) and obj and not self._is_own_association_page(request, obj):
            return [AssociationPresidentInline, CabinetInline]
        return self.inlines

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        is_other_assoc_for_assoc_admin = (
            self.is_association_admin(request) and obj and not self._is_own_association_page(request, obj)
        )

        members_count = Membership.objects.filter(association=obj).values("member_id").distinct().count()
        events_count = Event.objects.filter(association=obj).count()
        total_collected = (
            Payment.objects.filter(membership__association=obj).aggregate(total=Sum("amount_paid"))["total"] or 0
        )

        stats_cards = []

        if is_other_assoc_for_assoc_admin:
            extra_context["stats_cards"] = stats_cards
            return super().change_view(request, object_id, form_url, extra_context=extra_context)

        # always allowed cards (for everyone who can view this association)
        stats_cards.append({"label": "Total Members", "value": members_count})
        stats_cards.append({"label": "Total Events Posted", "value": events_count})

        # only dean/guild/superuser OR association admin on own association can see collections
        show_collections = False
        if request.user.is_superuser or self.is_guild_admin(request) or self.is_dean(request):
            show_collections = True
        elif self.is_association_admin(request):
            own_assoc = request.user.association_admin.association
            show_collections = (own_assoc.id == obj.id)

        if show_collections:
            stats_cards.append({"label": "Total Fees Collected", "value": total_collected})

        extra_context["stats_cards"] = stats_cards
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    
    def save_model(self, request, obj, form, change):
        if self.is_association_admin(request) and not (request.user.is_superuser or self.is_guild_admin(request)):
            own_assoc = request.user.association_admin.association
            if obj.id != own_assoc.id:
                raise PermissionDenied("You can only edit your own association.")
        super().save_model(request, obj, form, change)

@admin.register(Member)
class MemberAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    search_fields = ("registration_number", "email", "phone", "first_name", "last_name", "national_id_number")
    list_display = ("first_name", "last_name", "registration_number", "email", "phone", "member_type")
    readonly_fields = ("created_at", "created_by", "created_in_association")
    ordering = ("first_name", "last_name")
    list_filter = ("member_type", "faculty", "course")

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return hasattr(request.user, "guild") or hasattr(request.user, "dean")

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser or hasattr(request.user, "guild") or hasattr(request.user, "dean"):
            return True
        
        try:
            match = resolve(request.path_info)
            if match.url_name == "autocomplete":
                app_label = request.GET.get("app_label")
                model_name = request.GET.get("model_name")
                field_name = request.GET.get("field_name")
                if app_label == "campus_nexus" and model_name == "membership" and field_name == "member":
                    return True
        except Exception:
            pass
        
        return False

    def has_add_permission(self, request):
        return request.user.is_superuser or self.is_guild_admin(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or self.is_guild_admin(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or self.is_guild_admin(request)

    # Filter autocomplete ONLY for CabinetMember.member
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        assoc_admin = getattr(request.user, "association_admin", None)
        if not assoc_admin:
            return queryset, use_distinct

        assoc = assoc_admin.association
        model_name = request.GET.get("model_name")   # e.g. "cabinetmember"
        field_name = request.GET.get("field_name")   # e.g. "member"

        # Cabinet member selection: ONLY members who already have membership in this association
        if model_name == "cabinetmember" and field_name == "member":
            queryset = queryset.filter(memberships__association=assoc).distinct()
            return queryset, True

        # Everything else: keep normal access
        return queryset, use_distinct

@admin.register(Membership)
class MembershipAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("member", "association", "status", "joined_at", "subscription_anchor_date")
    ordering = ("-joined_at",)
    autocomplete_fields = ("member",)

    list_filter = (
        "status",
        "member__member_type",
        "member__faculty",
        "member__course",
        "joined_at",
    )
    search_fields = (
        "member__registration_number",
        "member__first_name",
        "member__last_name",
        "member__email",
        "member__phone",
        "association__name",    )

    class MembershipAdminForm(forms.ModelForm):
        class Meta:
            model = Membership
            fields = ("member", "association", "status", "subscription_anchor_date")

        def __init__(self, *args, **kwargs):
            self.request = kwargs.pop("request", None)
            super().__init__(*args, **kwargs)

            assoc_admin = getattr(getattr(self.request, "user", None), "association_admin", None)

            if assoc_admin:
                self.instance.association = assoc_admin.association
                if "association" in self.fields:
                    self.fields.pop("association")

            if "subscription_anchor_date" in self.fields:
                self.fields["subscription_anchor_date"].label = "Subscription start date"
                self.fields["subscription_anchor_date"].help_text = (
                    "Used to calculate subscription cycles. Leave blank to use today."
                )

        def clean(self):
            cleaned = super().clean()
            association = cleaned.get("association") or getattr(self.instance, "association", None)
            member = cleaned.get("member")

            if member and association and getattr(association, "faculty_id", None):
                if member.faculty_id != association.faculty_id:
                    raise ValidationError({
                        "member": (
                            f"{member.full_name} belongs to {member.faculty}, "
                            f"but this association is restricted to {association.faculty}."
                        )
                    })

            return cleaned

    form = MembershipAdminForm

    def get_form(self, request, obj=None, change=False, **kwargs):
        Form = super().get_form(request, obj, change=change, **kwargs)

        class RequestInjectedForm(Form):
            def __init__(self, *args, **kw):
                kw["request"] = request
                super().__init__(*args, **kw)

        return RequestInjectedForm

    # -----------------------------
    # Permissions
    # -----------------------------
    def has_module_permission(self, request):
        return (
            request.user.is_superuser
            or self.is_guild_admin(request)
            or self.is_association_admin(request)
            or self.is_dean(request)
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        if self.is_dean(request):
            return False
        return request.user.is_superuser or self.is_association_admin(request)

    def has_change_permission(self, request, obj=None):
        if self.is_dean(request):
            return False
        return request.user.is_superuser or self.is_association_admin(request)

    def has_delete_permission(self, request, obj=None):
        if self.is_dean(request):
            return False
        return request.user.is_superuser or self.is_association_admin(request)

    # -----------------------------
    # Queryset scoping
    # -----------------------------
    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("member", "association")

        if request.user.is_superuser or self.is_guild_admin(request) or self.is_dean(request):
            return qs

        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin:
            return qs.filter(association=assoc_admin.association)

        return qs.none()

    # -----------------------------
    # Cleaner UI
    # -----------------------------
    def get_fieldsets(self, request, obj=None):
        """
        - On ADD: hide status (auto Active).
        - On CHANGE: show status (in case they suspend/discard later).
        - Show association field only to superuser/guild/dean.
        """
        fields = ["member", "subscription_anchor_date"]

        if obj is not None:
            fields.insert(1, "status")  # show status only on edit

        if request.user.is_superuser or self.is_guild_admin(request) or self.is_dean(request):
            fields.insert(1, "association")

        return (("Membership", {"fields": fields}),)

    # -----------------------------
    # Save behavior
    # -----------------------------
    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None
        old_status = None
        if change and obj.pk:
            old_status = Membership.objects.filter(pk=obj.pk).values_list("status", flat=True).first()

        if self.is_association_admin(request) and not (request.user.is_superuser or self.is_guild_admin(request)):
            obj.association = request.user.association_admin.association

        if not obj.subscription_anchor_date:
            obj.subscription_anchor_date = timezone.localdate()

        # Auto status on create
        if is_new:
            obj.status = "active"

        super().save_model(request, obj, form, change)
        if is_new:
            action = "membership_created"
        elif old_status != obj.status:
            action = "membership_status_changed"
        else:
            action = "membership_updated"
        record_audit_event(
            actor=request.user,
            action=action,
            obj=obj,
            metadata={
                "old_status": old_status or "",
                "new_status": str(obj.status),
            },
        )

@admin.register(Cabinet)
class CabinetAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    inlines = [CabinetMemberInline]
    list_display = ("association", "year")
    search_fields = ("year", "association__name")
    list_filter = ("association",)

    def has_module_permission(self, request):
        return (
            request.user.is_superuser
            or self.is_guild_admin(request)
            or self.is_dean(request)
            or self.is_association_admin(request)
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        if self.is_dean(request):
            return False
        return request.user.is_superuser or self.is_guild_admin(request) or self.is_association_admin(request)

    def has_change_permission(self, request, obj=None):
        if self.is_dean(request):
            return obj is None  # allow list view only
        return request.user.is_superuser or self.is_guild_admin(request) or self.is_association_admin(request)

    def has_delete_permission(self, request, obj=None):
        if self.is_dean(request):
            return False
        return request.user.is_superuser or self.is_guild_admin(request) or self.is_association_admin(request)

    def get_exclude(self, request, obj=None):
        excluded = list(super().get_exclude(request, obj) or ())
        if self.is_association_admin(request) and not self.is_guild_admin(request):
            excluded.append("association")
        return tuple(excluded)

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Superuser/Guild/Dean: view all cabinets
        if request.user.is_superuser or self.is_guild_admin(request) or self.is_dean(request):
            return qs

        # Association admin: only own association
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin:
            return qs.filter(association=assoc_admin.association)

        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "association" and self.is_association_admin(request) and not self.is_guild_admin(request):
            assoc = request.user.association_admin.association
            kwargs["queryset"] = Association.objects.filter(id=assoc.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        # Dean: everything readonly
        if self.is_dean(request) and not request.user.is_superuser:
            return [f.name for f in self.model._meta.fields]

        if self.is_association_admin(request) and not self.is_guild_admin(request):
            return ("association",)

        return super().get_readonly_fields(request, obj)

    def save_model(self, request, obj, form, change):
        if self.is_association_admin(request) and not (request.user.is_superuser or self.is_guild_admin(request)):
            obj.association = request.user.association_admin.association
        super().save_model(request, obj, form, change)

class AssociationListFilter(admin.SimpleListFilter, CheckUserIdentityMixin):
    title = "Association"
    parameter_name = "association"

    def lookups(self, request, model_admin):
        if self.is_association_admin(request):
            assoc = request.user.association_admin.association
            return [(assoc.id, assoc.name)]
        return []

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(association__id=self.value())
        return queryset

@admin.register(CabinetMember)
class CabinetMemberAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("cabinet", "member", "role")
    list_filter = ("role", "cabinet__association", "cabinet__year")
    ordering = ("-cabinet__year", "role")
    autocomplete_fields = ("member", "cabinet")

    def has_module_permission(self, request):
        return (
            request.user.is_superuser
            or self.is_guild_admin(request)
            or self.is_dean(request)
            or self.is_association_admin(request)
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        if self.is_dean(request):
            return False
        return request.user.is_superuser or self.is_guild_admin(request) or self.is_association_admin(request)

    def has_change_permission(self, request, obj=None):
        if self.is_dean(request):
            return obj is None
        return request.user.is_superuser or self.is_guild_admin(request) or self.is_association_admin(request)

    def has_delete_permission(self, request, obj=None):
        if self.is_dean(request):
            return False
        return request.user.is_superuser or self.is_guild_admin(request) or self.is_association_admin(request)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("cabinet", "cabinet__association", "member")

        # Superuser/Guild/Dean: all
        if request.user.is_superuser or self.is_guild_admin(request) or self.is_dean(request):
            return qs

        # Association admin: only their association
        if assoc_admin := self.is_association_admin(request):
            return qs.filter(cabinet__association=assoc_admin.association)

        return qs.none()
    
    
SUB_FIELDS = (
    "duration_months",
    "grace_days",
    # "reminder_days_before_due",
    "max_missed_cycles",
    "allow_installments",
)


class FeeAdminForm(forms.ModelForm):
    """
    - For Association Admins: association field is removed and auto-set in admin.save_model()
    - Subscription rules enforced only when fee_type == 'subscription'
    """

    class Meta:
        model = Fee
        fields = "__all__"
        exclude = ("reminder_days_before_due",)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Help texts
        help_texts = {
            "duration_months": "Subscription only. E.g. 4 means pay every 4 months. 12 means yearly.",
            "grace_days": "Subscription only. Extra days after due date before marking overdue.",
            "reminder_days_before_due": "Subscription only. Example: [14, 3] sends reminders 14 and 3 days before due.",
            "max_missed_cycles": "Subscription only. After this many missed cycles, member can be marked inactive.",
            "allow_installments": "Subscription only. Allow partial payments to clear the charge.",
        }
        for field_name, text in help_texts.items():
            if field_name in self.fields:
                self.fields[field_name].help_text = text

        # If association admin: remove association field (since they are already inside their association)
        user = getattr(self.request, "user", None)
        assoc_admin = getattr(user, "association_admin", None) if user else None
        if assoc_admin and "association" in self.fields:
            self.fields.pop("association")

        # These are policy fields: avoid field-level "required" errors when hidden by JS.
        for field_name in SUB_FIELDS:
            if field_name in self.fields:
                self.fields[field_name].required = False

        fee_type = self._selected_fee_type()
        if fee_type == "membership":
            for f in SUB_FIELDS:
                if f in self.fields:
                    self.fields[f].required = False

    def _selected_fee_type(self):
        if self.is_bound:
            return self.data.get(self.add_prefix("fee_type"))
        return self.initial.get("fee_type") or getattr(self.instance, "fee_type", None)

    def clean(self):
        cleaned = super().clean()
        fee_type = cleaned.get("fee_type") or self._selected_fee_type()

        if fee_type == "subscription":
            duration = cleaned.get("duration_months") or 0
            if duration <= 0:
                raise ValidationError({
                    "duration_months": "Required for Subscription. Enter months (e.g. 4 or 12)."
                })

            missed = cleaned.get("max_missed_cycles")
            if missed is None or missed < 1:
                raise ValidationError({
                    "max_missed_cycles": "Required for Subscription. Must be at least 1."
                })

            if "reminder_days_before_due" in self.fields:
                days = cleaned.get("reminder_days_before_due") or []
                if not isinstance(days, list) or any((not isinstance(x, int) or x < 0) for x in days):
                    raise ValidationError({
                        "reminder_days_before_due": "Enter a JSON list of non-negative integers. Example: [14, 3]."
                    })
            else:
                cleaned["reminder_days_before_due"] = cleaned.get("reminder_days_before_due") or []

        else:
            # membership fee: reset subscription policy fields to safe defaults
            cleaned["duration_months"] = 0
            cleaned["grace_days"] = 0
            cleaned["reminder_days_before_due"] = []
            cleaned["max_missed_cycles"] = 0
            cleaned["allow_installments"] = True

        return cleaned


@admin.register(Fee)
class FeeAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    form = FeeAdminForm

    list_display = ("association", "fee_type", "amount", "duration_months", "created_at")
    list_filter = ("fee_type", "association", "created_at")
    ordering = ("-created_at",)
    search_fields = ("association__name", "fee_type")
    readonly_fields = ("created_at",)

    class Media:
        js = ("js/fee_form.js",)

    # ---- Inject request into the form (so it can hide association field) ----
    def get_form(self, request, obj=None, **kwargs):
        Form = super().get_form(request, obj, **kwargs)

        class RequestInjectedForm(Form):
            def __init__(self, *args, **kw):
                kw["request"] = request
                super().__init__(*args, **kw)

        return RequestInjectedForm

    # ---- Permissions ----
    def has_module_permission(self, request):
        return (
            request.user.is_superuser
            or self.is_guild_admin(request)
            or self.is_dean(request)
            or self.is_association_admin(request)
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        if self.is_dean(request):
            return False
        return request.user.is_superuser or self.is_guild_admin(request) or self.is_association_admin(request)

    def has_change_permission(self, request, obj=None):
        if self.is_dean(request):
            return obj is None
        return request.user.is_superuser or self.is_guild_admin(request) or self.is_association_admin(request)

    def has_delete_permission(self, request, obj=None):
        if self.is_dean(request):
            return False
        return request.user.is_superuser or self.is_guild_admin(request)

    # ---- Fields shown ----
    def get_fields(self, request, obj=None):
        fields = ["association", "fee_type", "amount"] + list(SUB_FIELDS) + ["created_at"]

        # Association admin should NOT see association field
        if self.is_association_admin(request) and not (request.user.is_superuser or self.is_guild_admin(request)):
            if "association" in fields:
                fields.remove("association")

        return fields

    # ---- Scoping ----
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Superuser/Guild/Dean: see all
        if request.user.is_superuser or self.is_guild_admin(request) or self.is_dean(request):
            return qs

        # Association admin: only own association
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin:
            return qs.filter(association=assoc_admin.association)

        return qs.none()

    # ---- Auto-set association ----
    def save_model(self, request, obj, form, change):
        old_obj = None
        if change and obj.pk:
            old_obj = Fee.objects.filter(pk=obj.pk).first()

        if self.is_association_admin(request) and not (request.user.is_superuser or self.is_guild_admin(request)):
            obj.association = request.user.association_admin.association
        super().save_model(request, obj, form, change)
        record_audit_event(
            actor=request.user,
            action="fee_updated" if change else "fee_created",
            obj=obj,
            metadata={
                "fee_type": str(obj.fee_type),
                "amount": str(obj.amount),
                "previous_amount": str(old_obj.amount) if old_obj else "",
            },
        )

    def delete_model(self, request, obj):
        record_audit_event(
            actor=request.user,
            action="fee_deleted",
            obj=obj,
            metadata={"fee_type": str(obj.fee_type), "amount": str(obj.amount)},
        )
        super().delete_model(request, obj)

@admin.register(Charge)
class ChargeAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    """
    Charges are system-generated “what a member owes”.
    Payments attach to charges and clear them partially/fully.

    - Association admins can view charges for their association only.
    - Superuser can view all + edit if necessary.
    - Includes changelist buttons to send reminders.
    """

    change_list_template = "admin/campus_nexus/charge/change_list.html"

    list_display = (
        "member_name",
        "association",
        "fee",
        "purpose",
        "period",
        "amount_due",
        "amount_paid_col",
        "balance_col",
        "status",
        "due_date",
        "is_overdue",
    )
    list_filter = (
        "status",
        "is_overdue",
        "purpose",
        "fee__fee_type",
        "association",
    )
    search_fields = (
        "membership__member__registration_number",
        "membership__member__first_name",
        "membership__member__last_name",
        "membership__member__email",
        "association__name",
    )
    ordering = ("-due_date", "-created_at")

    readonly_fields = (
        "created_at",
        "created_by",
        "association",
        "membership",
        "fee",
        "purpose",
        "title",
        "description",
        "amount_due",
        "due_date",
        "period_start",
        "period_end",
        "status",
        "is_overdue",
    )

    actions = ["send_subscription_reminders_selected"]

    # ---------------------------
    # Permissions (privacy lock)
    # ---------------------------
    def has_module_permission(self, request):
        return request.user.is_superuser or bool(self.is_association_admin(request))

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        # charges are system-generated; superuser only
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        # avoid tampering
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    # ---------------------------
    # Custom button URLs (views)
    # ---------------------------
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "send-reminders/",
                self.admin_site.admin_view(self.send_reminders_view),
                name="campus_nexus_charge_send_reminders",
            )
        ]
        return custom + urls

    def send_reminders_view(self, request):
        """
        Changelist buttons hit this endpoint.
        scope can be: due_soon | overdue
        """
        if not (request.user.is_superuser or self.is_association_admin(request)):
            self.message_user(request, "You are not allowed to perform this action.", level=messages.ERROR)
            return redirect("..")

        scope = request.GET.get("scope", "due_soon")
        today = timezone.localdate()
        due_soon_cutoff = today + timedelta(days=3)

        qs = Charge.objects.select_related("membership__member", "association", "fee").annotate(
            paid_total=Sum("payments__amount_paid")
        )

        # scope data to association admin
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin and not request.user.is_superuser:
            assoc_id = assoc_admin.association_id

            # keep status/overdue fresh & ensure current cycle exists (your existing behavior)
            recompute_overdue_flags_for_association(assoc_id)
            for m in assoc_admin.association.memberships.all().select_related("association"):
                ensure_current_subscription_charge(m)

            qs = qs.filter(association_id=assoc_id)

        # only subscription charges that are not cleared
        qs = qs.filter(
            purpose="subscription_fee",
            status__in=["unpaid", "partial"],
            due_date__isnull=False,
        )

        if scope == "overdue":
            qs = qs.filter(due_date__lt=today)
            title = "overdue"
        else:
            qs = qs.filter(due_date__gte=today, due_date__lte=due_soon_cutoff)
            title = "due in 3 days"

        sent = 0
        missing = 0

        for c in qs:
            # extra safety: ignore if cleared by any chance
            if c.balance <= 0:
                continue

            days_left = (c.due_date - today).days
            ok = send_subscription_reminder_email(
                member=c.membership.member,
                association=c.association,
                charge=c,
                days_left=days_left,
            )
            if ok:
                sent += 1
            else:
                missing += 1

        self.message_user(
            request,
            f"Reminder run complete ({title}). Emails sent: {sent}. Missing member email: {missing}.",
            level=messages.SUCCESS,
        )
        return redirect("..")

    # ---------------------------
    # Queryset scoping
    # ---------------------------
    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("membership", "membership__member", "association", "fee")
            .annotate(paid_total=Sum("payments__amount_paid"))
        )

        if request.user.is_superuser:
            return qs

        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin:
            # Keep fresh for their association
            recompute_overdue_flags_for_association(assoc_admin.association_id)

            # Ensure current cycle exists (you already do this)
            for m in assoc_admin.association.memberships.all().select_related("association"):
                ensure_current_subscription_charge(m)

            return qs.filter(association=assoc_admin.association)

        return qs.none()

    # ---------------------------
    # Columns helpers
    # ---------------------------
    def member_name(self, obj):
        return obj.membership.member.full_name
    member_name.short_description = "Member"

    def period(self, obj):
        if obj.period_start and obj.period_end:
            return f"{obj.period_start} → {obj.period_end}"
        return "—"
    period.short_description = "Period"

    def amount_paid_col(self, obj):
        return f"{obj.amount_paid_total}"
    amount_paid_col.short_description = "Paid"

    def balance_col(self, obj):
        bal = obj.balance
        if bal <= 0:
            return format_html("<b style='color:green;'>0</b>")
        return format_html("<b style='color:#b45309;'>{}</b>", bal)
    balance_col.short_description = "Balance"

    # ---------------------------
    # Admin action (selected)
    # ---------------------------
    @admin.action(description="Send subscription reminder email (selected)")
    def send_subscription_reminders_selected(self, request, queryset):
        today = timezone.localdate()
        sent = 0
        missing = 0

        for c in queryset.select_related("membership__member", "association"):
            if c.purpose != "subscription_fee":
                continue
            if not c.due_date:
                continue
            if c.balance <= 0:
                continue

            days_left = (c.due_date - today).days
            ok = send_subscription_reminder_email(
                member=c.membership.member,
                association=c.association,
                charge=c,
                days_left=days_left,
            )
            if ok:
                sent += 1
            else:
                missing += 1

        self.message_user(
            request,
            f"Selected reminders sent: {sent}. Members missing email: {missing}.",
            level=messages.SUCCESS,
        )
class PaymentAdminForm(forms.ModelForm):
    """
    Treasurer UX:
    - Always pick Membership
    - Either pick Fee (recommended)
    - OR fill custom fields (event/merch/donation/other)
    Charge is created automatically.
    """

    # Extra fields for custom charges
    purpose = forms.ChoiceField(choices=Charge.PURPOSE_CHOICES, required=False)
    title = forms.CharField(required=False)
    amount_due = forms.DecimalField(required=False, max_digits=12, decimal_places=2)
    due_date = forms.DateField(required=False)

    class Meta:
        model = Payment
        # Exclude charge — it is auto-created
        fields = (
            "membership",
            "fee",
            "amount_paid",
            "paid_at",
            "payment_method",
            "reference_code",
            "receipt_image",
            "note",
            "status",
        )

    def clean(self):
        cleaned = super().clean()

        membership = cleaned.get("membership")
        fee = cleaned.get("fee")

        # Custom inputs
        purpose = self.cleaned_data.get("purpose")
        title = self.cleaned_data.get("title")
        amount_due = self.cleaned_data.get("amount_due")
        due_date = self.cleaned_data.get("due_date")

        if not membership:
            raise ValidationError({"membership": "Membership is required."})

        # If fee is selected, ignore custom fields
        if fee:
            # Optional: ensure fee belongs to same association
            if fee.association_id != membership.association_id:
                raise ValidationError({"fee": "Selected fee must belong to the same association as the membership."})
            return cleaned
        
        if fee and fee.fee_type == "subscription" and (fee.duration_months or 0) <= 0:
            raise ValidationError({"fee": "Subscription fee must have duration_months set (e.g. 4 for Coder's, 12 for FOSSA)."})


        # No fee selected, then user must provide custom charge info
        if not purpose:
            raise ValidationError({"purpose": "Select what this payment is for (event/merch/donation/other)."})
        if not amount_due:
            raise ValidationError({"amount_due": "Enter the total amount due for this item."})
        if not title:
            raise ValidationError({"title": "Enter a title (e.g., Dinner Ticket, Hoodie, Donation)."})
        # due_date optional

        return cleaned

@admin.register(Payment)
class PaymentAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    form = PaymentAdminForm

    list_display = ("membership", "paid_at", "fee", "amount_paid", "status")
    ordering = ("-paid_at",)
    search_fields = (
        "membership__member__registration_number",
        "membership__member__first_name",
        "membership__member__last_name",
        "membership__member__email",
        "fee__association__name",
    )
    list_select_related = ("membership", "membership__member", "fee", "charge")

    def get_list_filter(self, request):
        """
        Assoc admins don't need (fee__association) filter because they are already scoped.
        Superuser can keep it for global reporting.
        """
        if request.user.is_superuser:
            return ("paid_at", "status", "fee__association")
        return ("paid_at", "status")

    # ---------------------------
    # Permissions (privacy lock)
    # ---------------------------
    def has_module_permission(self, request):
        # Only superuser + association admins see Payments module at all
        return request.user.is_superuser or bool(self.is_association_admin(request))

    def has_view_permission(self, request, obj=None):
        # Dean/Guild: no access at all (also blocks direct URL access)
        if self.is_dean(request) or self.is_guild_admin(request):
            return False

        if request.user.is_superuser:
            return True

        assoc_admin = self.is_association_admin(request)
        if not assoc_admin:
            return False

        # Object-level: only own association
        if obj is not None:
            return obj.membership.association_id == assoc_admin.association_id
        return True

    def has_add_permission(self, request):
        if self.is_dean(request) or self.is_guild_admin(request):
            return False
        return request.user.is_superuser or bool(self.is_association_admin(request))

    def has_change_permission(self, request, obj=None):
        if self.is_dean(request) or self.is_guild_admin(request):
            return False

        if request.user.is_superuser:
            return True

        assoc_admin = self.is_association_admin(request)
        if not assoc_admin:
            return False

        if obj is not None:
            return obj.membership.association_id == assoc_admin.association_id
        return True

    def has_delete_permission(self, request, obj=None):
        if self.is_dean(request) or self.is_guild_admin(request):
            return False

        if request.user.is_superuser:
            return True

        assoc_admin = self.is_association_admin(request)
        if not assoc_admin:
            return False

        if obj is not None:
            return obj.membership.association_id == assoc_admin.association_id
        return True

    # ---------------------------
    # Scoping
    # ---------------------------
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Only association admins get scoped choices
        if self.is_association_admin(request) and not request.user.is_superuser:
            assoc = request.user.association_admin.association

            if db_field.name == "membership":
                kwargs["queryset"] = Membership.objects.filter(association=assoc)

            if db_field.name == "fee":
                kwargs["queryset"] = Fee.objects.filter(association=assoc)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            "membership", "membership__member", "fee", "charge"
        )

        # Superuser: everything
        if request.user.is_superuser:
            return qs

        # Dean/Guild: nothing (even if they guess the URL)
        if self.is_dean(request) or self.is_guild_admin(request):
            return qs.none()

        # Association admin: only own association
        if assoc_admin := self.is_association_admin(request):
            return qs.filter(membership__association=assoc_admin.association)

        return qs.none()

    # ---------------------------
    # Save + auto charge + email
    # ---------------------------
    @transaction.atomic
    def save_model(self, request, obj, form, change):
        """
        Auto-create or reuse Charge based on the form:
        - If fee selected → reuse/create fee charge (subscription -> current cycle)
        - Else → create a custom charge (event/merch/donation/other)
        """
        old_status = None
        if change and obj.pk:
            old_status = Payment.objects.filter(pk=obj.pk).values_list("status", flat=True).first()

        # HARD SAFETY: association admins can only record for their association
        if not request.user.is_superuser:
            assoc_admin = self.is_association_admin(request)
            if not assoc_admin:
                raise PermissionDenied("You are not allowed to record payments.")
            if obj.membership.association_id != assoc_admin.association_id:
                raise PermissionDenied("You can only record payments for your association.")

        # Always record who entered it
        if not obj.recorded_by_id:
            obj.recorded_by = request.user

        membership = obj.membership
        fee = obj.fee

        if not obj.charge_id:
            if fee:
                charge = get_or_create_charge_for_fee(
                    membership=membership,
                    fee=fee,
                    user=request.user,
                )
            else:
                charge = create_charge_custom(
                    membership=membership,
                    purpose=form.cleaned_data.get("purpose"),
                    title=form.cleaned_data.get("title"),
                    amount_due=form.cleaned_data.get("amount_due"),
                    due_date=form.cleaned_data.get("due_date"),
                    description=form.cleaned_data.get("note") or "",
                    user=request.user,
                )
            obj.charge = charge

        super().save_model(request, obj, form, change)

        # Recompute charge status after saving payment
        if obj.charge_id:
            obj.charge.recompute_status()
            obj.charge.save(update_fields=["status"])

        # Email notification after commit
        transaction.on_commit(lambda: send_payment_recorded_email(
            member=obj.membership.member,
            association=obj.membership.association,
            payment=obj,
            charge=obj.charge,
        ))
        record_audit_event(
            actor=request.user,
            action="payment_recorded" if not change else "payment_updated",
            obj=obj,
            metadata={
                "amount_paid": str(obj.amount_paid),
                "status": str(obj.status),
                "charge_id": str(obj.charge_id or ""),
            },
        )
        if old_status != "reversed" and obj.status == "reversed":
            record_audit_event(
                actor=request.user,
                action="payment_reversed",
                obj=obj,
                metadata={"previous_status": str(old_status or "")},
            )

@admin.register(Event)
class EventAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("title", "association", "event_date", "created_at", "venue", "posted_by")
    list_filter = (AssociationListFilter, "event_date")
    ordering = ("-created_at",)
    exclude = ("id",)

    def has_module_permission(self, request):
        return (
            request.user.is_superuser
            or self.is_guild_admin(request)
            or self.is_dean(request)
            or self.is_association_admin(request)
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        # Dean remains view-only
        return (
            request.user.is_superuser
            or self.is_guild_admin(request)
            or self.is_association_admin(request)
        )

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser or self.is_guild_admin(request):
            return True
        if self.is_dean(request):
            return False
        if not self.is_association_admin(request):
            return False
        if obj is None:
            return True  # allow access to list page
        assoc = request.user.association_admin.association
        return obj.association_id == assoc.id

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser or self.is_guild_admin(request):
            return True
        if self.is_dean(request):
            return False
        if not self.is_association_admin(request):
            return False
        if obj is None:
            return False
        assoc = request.user.association_admin.association
        return obj.association_id == assoc.id

    # Everyone can view all events (system-wide feed)
    def get_queryset(self, request):
        return super().get_queryset(request)

    # Association admins should not choose association manually
    def get_exclude(self, request, obj=None):
        excluded = list(super().get_exclude(request, obj) or ())
        if self.is_association_admin(request) and not self.is_guild_admin(request):
            excluded.append("association")
        return tuple(excluded)
    
    def get_readonly_fields(self, request, obj=None):
        if self.is_association_admin(request) and obj:
            assoc = request.user.association_admin.association
            if obj.association_id != assoc.id:
                return [f.name for f in self.model._meta.fields]
        return super().get_readonly_fields(request, obj)


    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        assoc_admin = getattr(request.user, "association_admin", None)

        # Lock association for association admins
        if db_field.name == "association" and assoc_admin and not self.is_guild_admin(request):
            assoc = assoc_admin.association
            kwargs["queryset"] = Association.objects.filter(id=assoc.id)

        # Key fix: posted_by must be a Membership in the same association
        if db_field.name == "posted_by" and assoc_admin and not self.is_guild_admin(request):
            assoc = assoc_admin.association
            kwargs["queryset"] = Membership.objects.filter(association=assoc)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        assoc_admin = getattr(request.user, "association_admin", None)

        # Association admin: force event association
        if assoc_admin and not (request.user.is_superuser or self.is_guild_admin(request)):
            obj.association = assoc_admin.association

        # Server-side validation: posted_by must belong to obj.association
        if obj.posted_by_id and obj.posted_by.association_id != obj.association_id:
            raise ValidationError("posted_by must be a membership in the same association as the event.")

        super().save_model(request, obj, form, change)


@admin.register(AuditLog)
class AuditLogAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("created_at", "action", "model_name", "object_repr", "actor", "association")
    list_filter = ("action", "model_name", "association", "created_at")
    search_fields = ("object_repr", "object_id", "actor__username", "association__name")
    readonly_fields = (
        "created_at",
        "action",
        "model_name",
        "object_id",
        "object_repr",
        "actor",
        "association",
        "metadata",
    )
    ordering = ("-created_at",)

    def has_module_permission(self, request):
        return request.user.is_superuser or bool(self.is_guild_admin(request))

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("subject", "association", "member", "submitted_by", "submitted_at")
    list_filter = ("association", "submitted_at")
    search_fields = ("subject", "message", "member__email", "member__registration_number", "submitted_by__username")
    readonly_fields = ("submitted_at", "submitted_by", "association", "member", "subject", "message")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
class FeedbackSubmitForm(forms.Form):
    subject = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "vTextField"}))
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 6, "class": "vLargeTextField"}))


def submit_feedback_view(request):
    """
    A custom admin page to submit feedback.
    - Any authenticated admin user can submit.
    - Feedback entries are only viewable by superuser (via FeedbackAdmin above).
    """
    if request.method == "POST":
        form = FeedbackSubmitForm(request.POST)
        if form.is_valid():
            obj = Feedback(
                subject=form.cleaned_data["subject"],
                message=form.cleaned_data["message"],
                submitted_by=request.user,
            )

            # If association admin, auto attach their association
            assoc_admin = getattr(request.user, "association_admin", None)
            if assoc_admin:
                obj.association = assoc_admin.association

            # If you ever link Member to User later, you can set obj.member here.
            # For now we leave obj.member optional.

            obj.save()

            messages.success(request, "Thanks! Your feedback has been submitted successfully.")
            return redirect("admin:index")
    else:
        form = FeedbackSubmitForm()

    context = dict(
        admin.site.each_context(request),
        title="Submit Feedback",
        form=form,
    )
    return TemplateResponse(request, "admin/submit_feedback.html", context)


# ---- register custom URL under /admin/submit-feedback/ ----
_original_get_urls = admin.site.get_urls

def _custom_get_urls():
    urls = _original_get_urls()
    custom = [
        path(
            "submit-feedback/",
            admin.site.admin_view(submit_feedback_view),
            name="submit_feedback",
        ),
    ]
    return custom + urls

admin.site.get_urls = _custom_get_urls


@admin.register(GuildCabinet)
class GuildCabinetAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    inlines = [GuildExecutiveInline]
    list_display = ("year", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("year",)
    ordering = ("-year",)

    def has_module_permission(self, request):
        return request.user.is_superuser or self.is_guild_admin(request) or self.is_dean(request) or self.is_association_admin(request)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return request.user.is_superuser or self.is_guild_admin(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or self.is_guild_admin(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def get_inline_instances(self, request, obj=None):
        return super().get_inline_instances(request, obj)
    
@admin.register(GuildExecutive)
class GuildExecutiveAdmin(admin.ModelAdmin):
    list_display = ("cabinet", "photo_thumb", "position_type", "ministry", "member", "reports_to")
    list_filter = ("cabinet", "position_type")
    search_fields = ("ministry", "member__first_name", "member__last_name", "member__registration_number")
    autocomplete_fields = ("member", "cabinet", "reports_to")
    ordering = ("-cabinet__year", "sort_order", "ministry", "member__first_name")

    def photo_thumb(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="width:34px;height:34px;border-radius:50%;object-fit:cover;" />',
                obj.photo.url
            )
        return "—"
    photo_thumb.short_description = "Photo"

@admin.register(Announcement)
class AnnouncementAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("title", "audience", "association", "faculty", "is_published", "created_at", "posted_by")
    list_filter = ("audience", "is_published", "association", "faculty", "created_at")
    search_fields = ("title", "message")
    readonly_fields = ("created_at", "posted_by")

    fieldsets = (
        (None, {"fields": ("title", "message")}),
        ("Audience & Targeting", {"fields": ("audience", "association", "faculty", "cabinet")}),
        ("Publishing", {"fields": ("is_published",)}),
        ("Audit", {"fields": ("posted_by", "created_at")}),
    )

    def has_module_permission(self, request):
        return (
            request.user.is_superuser
            or self.is_guild_admin(request)
            or self.is_association_admin(request)
            or self.is_dean(request)  # dean can view (we'll enforce read-only below)
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        # allow guild + association admins to add announcements
        return request.user.is_superuser or self.is_guild_admin(request) or self.is_association_admin(request)

    def has_change_permission(self, request, obj=None):
        # dean cannot edit anything
        if self.is_dean(request):
            return False

        # superuser/guild can edit all
        if request.user.is_superuser or self.is_guild_admin(request):
            return True

        # association admin: can only edit their own announcements
        if self.is_association_admin(request):
            if obj is None:
                return True
            return obj.posted_by_id == request.user.id

        return False

    def has_delete_permission(self, request, obj=None):
        # keep deletion only for superuser (safe)
        return request.user.is_superuser

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # superuser sees all
        if request.user.is_superuser:
            return qs

        # guild admin sees all
        if self.is_guild_admin(request):
            return qs

        # dean: ONLY published
        if self.is_dean(request):
            return qs.filter(is_published=True)

        # association admin:
        # - sees published global
        # - sees published for their association
        # - sees their own drafts/unpublished too
        assoc_admin = self.is_association_admin(request)
        if assoc_admin:
            assoc = assoc_admin.association
            return qs.filter(
                models.Q(is_published=True, audience="all")
                | models.Q(is_published=True, audience="association", association=assoc)
                | models.Q(posted_by=request.user)
            )

        return qs.none()

    def save_model(self, request, obj, form, change):
        if not change and not obj.posted_by_id:
            obj.posted_by = request.user

        # Association admins: force audience to association + lock association
        assoc_admin = self.is_association_admin(request)
        if assoc_admin and not (request.user.is_superuser or self.is_guild_admin(request)):
            obj.audience = "association"
            obj.association = assoc_admin.association
            obj.faculty = None

        super().save_model(request, obj, form, change)
