from dataclasses import fields
from urllib import request
from django.conf import settings
from django.contrib import admin
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.core.mail import send_mail
from django.db import transaction
from django.utils.html import format_html

from campus_nexus.models import *
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

class FeeInline(AssociationInlineGuardMixin, admin.TabularInline):
    model = Fee
    extra = 0
    show_change_link = False 
    fields = ("fee_type", "amount", "duration_months", "created_at")
    readonly_fields = ("created_at",)

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
class AssociationAdminAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("association", "user", "title")
    search_fields = ("association__name", "user__username", "user__first_name", "user__last_name")
    fields = ("association", "user", "title", "bio", "profile_photo")
    readonly_fields = ("association", "user")

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
        if request.user.is_superuser or self.is_guild_admin(request):
            return True
        if self.is_dean(request):
            return False

        assoc_admin = getattr(request.user, "association_admin", None)
        if not assoc_admin:
            return False

        if obj is None:
            return True
        return obj.pk == assoc_admin.pk

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

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)

        members_count = Membership.objects.filter(association=obj).values("member_id").distinct().count()
        events_count = Event.objects.filter(association=obj).count()
        total_collected = (
            Payment.objects.filter(membership__association=obj).aggregate(total=Sum("amount_paid"))["total"] or 0
        )

        stats_cards = []

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
    search_fields = ("registration_number", "email", "phone", "first_name", "last_name")
    list_display = ("first_name", "last_name", "registration_number", "email", "phone", "member_type")
    readonly_fields = ("created_at", "created_by", "created_in_association")
    ordering = ("first_name", "last_name")
    list_filter = ("member_type", "faculty", "course")

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

    # Filter autocomplete ONLY for CabinetMember.member
    #    (But do NOT block member browsing / membership assignment)
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
    list_display = ("member", "association", "joined_at", "status")
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
    )

    # -----------------------------
    # Request-aware ModelForm
    # -----------------------------
    class MembershipAdminForm(forms.ModelForm):
        class Meta:
            model = Membership
            fields = "__all__"

        def __init__(self, *args, **kwargs):
            self.request = kwargs.pop("request", None)
            super().__init__(*args, **kwargs)

            assoc_admin = getattr(getattr(self.request, "user", None), "association_admin", None)

            # Association admin: force association and hide the field
            if assoc_admin:
                # set early (prevents "Association is required")
                self.instance.association = assoc_admin.association

                if "association" in self.fields:
                    self.fields.pop("association")

        def clean(self):
            cleaned_data = super().clean()

            # determine association safely (field may be hidden for assoc admins)
            association = cleaned_data.get("association") or getattr(self.instance, "association", None)
            member = cleaned_data.get("member")

            # Faculty restriction validation (clear message on member field)
            if member and association and getattr(association, "faculty_id", None):
                if member.faculty_id != association.faculty_id:
                    raise ValidationError({
                        "member": (
                            f"{member} belongs to {member.faculty}, "
                            f"but this association is restricted to {association.faculty}."
                        )
                    })

            return cleaned_data

    form = MembershipAdminForm

    # Restrict member autocomplete ONLY for cabinet use was elsewhere.
    # For membership creation you may want broader search; keep this only if desired.
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # Correct request injection: subclass the actual ModelForm, not forms.Form
    def get_form(self, request, obj=None, **kwargs):
        Form = super().get_form(request, obj, **kwargs)

        class RequestInjectedForm(Form):
            def __init__(self, *args, **kw):
                kw["request"] = request
                super().__init__(*args, **kw)

        return RequestInjectedForm

    # Permissions (keep yours)
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
        return request.user.is_superuser or self.is_association_admin(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or self.is_association_admin(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or self.is_association_admin(request)

    def get_list_filter(self, request):
        lf = list(super().get_list_filter(request) or ())
        if self.is_association_admin(request) and "association" in lf:
            lf.remove("association")
        return tuple(lf)

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_superuser or self.is_guild_admin(request) or self.is_dean(request):
            return qs

        if assoc_admin := self.is_association_admin(request):
            return qs.filter(association=assoc_admin.association)

        return qs.none()

    def get_exclude(self, request, obj=None):
        excluded = list(super().get_exclude(request, obj) or ())
        if self.is_association_admin(request):
            excluded.append("association")
        return tuple(excluded)

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None

        if self.is_association_admin(request) and not (request.user.is_superuser or self.is_guild_admin(request)):
            obj.association = request.user.association_admin.association

        super().save_model(request, obj, form, change)

        # Email notification ONLY when a membership is created
        if is_new:
            member = obj.member
            association = obj.association

            subject = f"You've been added to {association.name} on Campus Nexus"
            message = (
                f"Hello {member.first_name},\n\n"
                f"You have been added as a member of '{association.name}' in Campus Nexus.\n\n"
                f"If you believe this was a mistake, please contact your association leadership.\n\n"
                f"Thank you,\n"
                f"Campus Nexus"
            )

            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@campusnexus.local")

            def _send():
                if member.email:
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=from_email,
                        recipient_list=[member.email],
                        fail_silently=True,  # keep admin stable even if email server is down
                    )

            transaction.on_commit(_send)
    
    def _email_membership_removed(self, membership: Membership):
        member = membership.member
        association = membership.association
        if not member.email:
            return

        subject = f"You've been removed from {association.name} on Campus Nexus"
        message = (
            f"Hello {member.first_name},\n\n"
            f"You have been removed from '{association.name}' on Campus Nexus.\n\n"
            f"If you believe this was a mistake, please contact your association leadership.\n\n"
            f"Regards,\n"
            f"Campus Nexus"
        )
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@campusnexus.local")

        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[member.email],
            fail_silently=True,
        )

    def delete_model(self, request, obj):
        # capture details before deletion
        membership = Membership.objects.select_related("member", "association").get(pk=obj.pk)

        super().delete_model(request, obj)

        transaction.on_commit(lambda: self._email_membership_removed(membership))

    def delete_queryset(self, request, queryset):
        # capture details before deletion (bulk)
        memberships = list(queryset.select_related("member", "association"))

        super().delete_queryset(request, queryset)

        transaction.on_commit(lambda: [self._email_membership_removed(m) for m in memberships])

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

@admin.register(Fee)
class FeeAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("association", "fee_type", "amount", "duration_months", "created_at")
    list_filter = ("fee_type", "association", "created_at")
    ordering = ("-created_at",)
    search_fields = ("association__name", "fee_type")

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
        return request.user.is_superuser or self.is_association_admin(request)

    def has_change_permission(self, request, obj=None):
        if self.is_dean(request):
            return obj is None
        return request.user.is_superuser or self.is_association_admin(request)

    def has_delete_permission(self, request, obj=None):
        if self.is_dean(request):
            return False
        return request.user.is_superuser or self.is_association_admin(request)

    def get_exclude(self, request, obj=None):
        excluded = list(super().get_exclude(request, obj) or ())
        if self.is_association_admin(request) and not self.is_guild_admin(request):
            excluded.append("association")
        return tuple(excluded)

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Superuser/Guild/Dean: view all fees
        if request.user.is_superuser or self.is_guild_admin(request) or self.is_dean(request):
            return qs

        # Association admin: only own association
        if assoc_admin := self.is_association_admin(request):
            return qs.filter(association=assoc_admin.association)

        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "association" and self.is_association_admin(request) and not self.is_guild_admin(request):
            assoc = request.user.association_admin.association
            kwargs["queryset"] = Association.objects.filter(id=assoc.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if self.is_association_admin(request) and not request.user.is_superuser and not self.is_guild_admin(request):
            obj.association = request.user.association_admin.association
        super().save_model(request, obj, form, change)

@admin.register(Charge)
class ChargeAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("membership", "association", "purpose", "amount_due", "amount_paid_total_display", "status", "created_at")
    list_filter = ("status", "purpose", "association")
    search_fields = (
        "membership__member__registration_number",
        "membership__member__first_name",
        "membership__member__last_name",
        "membership__member__email",
        "association__name",
        "title",
    )
    ordering = ("-created_at",)
    autocomplete_fields = ("membership", "fee")

    readonly_fields = ("status", "created_by", "created_at")

    def amount_paid_total_display(self, obj):
        return obj.amount_paid_total
    amount_paid_total_display.short_description = "Paid Total"

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
        return request.user.is_superuser or self.is_association_admin(request)

    def has_change_permission(self, request, obj=None):
        if self.is_dean(request):
            return obj is None
        if request.user.is_superuser or self.is_guild_admin(request):
            return True
        if not self.is_association_admin(request):
            return False
        if obj is None:
            return True
        return obj.association_id == request.user.association_admin.association_id

    def has_delete_permission(self, request, obj=None):
        if self.is_dean(request):
            return False
        return request.user.is_superuser

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Lock membership/fee choices to association for association admin
        if self.is_association_admin(request) and not self.is_guild_admin(request):
            assoc = request.user.association_admin.association

            if db_field.name == "membership":
                kwargs["queryset"] = Membership.objects.filter(association=assoc)

            if db_field.name == "fee":
                kwargs["queryset"] = Fee.objects.filter(association=assoc)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("membership", "membership__member", "association", "fee")
        if request.user.is_superuser or self.is_guild_admin(request) or self.is_dean(request):
            return qs
        if assoc_admin := self.is_association_admin(request):
            return qs.filter(association=assoc_admin.association)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user

        # Force association for association admin
        if self.is_association_admin(request) and not (request.user.is_superuser or self.is_guild_admin(request)):
            assoc = request.user.association_admin.association
            obj.association = assoc

        super().save_model(request, obj, form, change)

from django.core.mail import send_mail
from django.conf import settings

@admin.register(Payment)
class PaymentAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("membership", "paid_at", "charge", "amount_paid", "payment_method", "status")
    list_filter = ("paid_at", "status", "payment_method", "charge__association")
    ordering = ("-paid_at",)
    autocomplete_fields = ("membership", "charge", "fee")

    search_fields = (
        "membership__member__registration_number",
        "membership__member__first_name",
        "membership__member__last_name",
        "membership__member__email",
        "charge__association__name",
        "reference_code",
    )

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
        return request.user.is_superuser or self.is_association_admin(request)

    def has_change_permission(self, request, obj=None):
        if self.is_dean(request):
            return obj is None
        if request.user.is_superuser or self.is_guild_admin(request):
            return True
        if not self.is_association_admin(request):
            return False
        if obj is None:
            return True
        return obj.charge.association_id == request.user.association_admin.association_id

    def has_delete_permission(self, request, obj=None):
        if self.is_dean(request):
            return False
        return request.user.is_superuser

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if self.is_association_admin(request) and not self.is_guild_admin(request):
            assoc = request.user.association_admin.association

            if db_field.name == "membership":
                kwargs["queryset"] = Membership.objects.filter(association=assoc)

            if db_field.name == "charge":
                kwargs["queryset"] = Charge.objects.filter(association=assoc)

            if db_field.name == "fee":
                kwargs["queryset"] = Fee.objects.filter(association=assoc)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            "membership", "membership__member",
            "charge", "charge__association",
            "fee"
        )
        if request.user.is_superuser or self.is_guild_admin(request) or self.is_dean(request):
            return qs
        if assoc_admin := self.is_association_admin(request):
            return qs.filter(charge__association=assoc_admin.association)
        return qs.none()

    def save_model(self, request, obj, form, change):
        # Ensure audit
        if not obj.recorded_by_id:
            obj.recorded_by = request.user

        # Keep membership consistent with charge
        if obj.charge_id:
            obj.membership = obj.charge.membership
            if obj.charge.fee_id:
                obj.fee = obj.charge.fee

        super().save_model(request, obj, form, change)

        # After save: recompute charge status
        obj.charge.recompute_status()
        obj.charge.save(update_fields=["status"])

        # Notify member (email) — best effort, never crash admin
        member = obj.membership.member
        assoc = obj.charge.association
        purpose = obj.charge.title or obj.charge.get_purpose_display()

        if member.email:
            try:
                subject = f"Payment received — {assoc.name}"
                message = (
                    f"Hello {member.full_name},\n\n"
                    f"Your payment has been registered in Campus Nexus.\n\n"
                    f"Association: {assoc.name}\n"
                    f"Purpose: {purpose}\n"
                    f"Amount: {obj.amount_paid}\n"
                    f"Method: {obj.get_payment_method_display()}\n"
                    f"Reference: {obj.reference_code or 'N/A'}\n"
                    f"Date: {obj.paid_at:%Y-%m-%d %H:%M}\n\n"
                    f"Thank you.\n"
                    f"— Campus Nexus"
                )
                send_mail(
                    subject,
                    message,
                    getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    [member.email],
                    fail_silently=True,
                )
            except Exception:
                pass


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

@admin.register(Feedback)
class FeedbackAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("subject", "association", "member", "submitted_by", "submitted_at")
    list_filter = ("association", "submitted_at")
    search_fields = ("subject", "message", "member__email", "member__registration_number", "submitted_by__username")
    readonly_fields = ("submitted_at", "submitted_by")

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
        # Allow all platform roles to submit feedback
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        # Keep it simple: only superuser can edit feedback entries.
        # Everyone else can view + add only.
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        # ONLY superuser can delete
        return request.user.is_superuser

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Superuser / Guild / Dean see all feedback
        if request.user.is_superuser or self.is_guild_admin(request) or self.is_dean(request):
            return qs

        # Association admin sees:
        # - feedback for their association
        # - system-wide feedback (association is NULL)
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin:
            return qs.filter(
                models.Q(association=assoc_admin.association) | models.Q(association__isnull=True)
            )
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not change and not obj.submitted_by_id:
            obj.submitted_by = request.user

        # Association admin: auto-attach their association if missing
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin and not obj.association_id:
            obj.association = assoc_admin.association

        super().save_model(request, obj, form, change)

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

@admin.register(GuildAnnouncement)
class GuildAnnouncementAdmin(CheckUserIdentityMixin, admin.ModelAdmin):
    list_display = ("title", "cabinet", "is_published", "created_at", "posted_by")
    list_filter = ("is_published", "cabinet", "created_at")
    search_fields = ("title", "message")
    readonly_fields = ("created_at", "posted_by")

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
        return request.user.is_superuser

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Everyone can see published announcements
        if request.user.is_superuser or self.is_guild_admin(request):
            return qs
        return qs.filter(is_published=True)

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
