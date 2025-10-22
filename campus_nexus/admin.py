from django.contrib import admin
from campus_nexus.models import (
    Faculty,
    Course,
    Association,
    Member,
    Cabinet,
    Payment,
    Event,
    Fee,
    Membership,
    CabinetMember,
    AssociationAdmin,
    Feedback,
)

class CheckUserIdentityMixin:

    def is_superuser(self, request):
        return request.user.is_superuser

    def is_association_admin(self, request):
        return getattr(request.user, "association_admin", None)
    
    def is_guild_admin(self, request):
        return getattr(request.user, "guild", None)
    

@admin.register(Guild)
class GuildAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user__username',)
    ordering = ('user__username',)
    raw_id_fields = ('user',)

@admin.register(AssociationAdmin)
class AssocationAdminAdmin(admin.ModelAdmin):
    list_display = ('user', 'association')
    search_fields = ('user__username', 'association__name')
    list_filter = ('association',)
    ordering = ('user__username',)
    raw_id_fields = ('user', 'association')

@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    # search_fields = ('name',)
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_years', 'faculty', 'created_at')
    # search_fields = ('name',)
    list_filter = ('faculty',)
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(Association)
class AssociationAdmin(admin.ModelAdmin, CheckUserIdentityMixin):
    list_display = ('name', 'faculty', 'created_at', 'description',)
    search_fields = ('name',)
    list_filter = ('faculty',)
    ordering = ('-created_at',)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser or self.is_guild_admin(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin, CheckUserIdentityMixin):
    list_display = ('full_name', 'email', 'member_type', 'faculty', 'course', 'created_at',)

    list_filter = ('member_type', 'faculty', 'course')
    search_fields = ("first_name", "last_name", "registration_number")
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj = None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj = None):
        return request.user.is_superuser


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin, CheckUserIdentityMixin):
    list_display = ('member', 'association', 'joined_at', 'status')
    # search_fields = ('member__full_name', 'association__name')
    list_filter = ('association', 'status')
    ordering = ('-joined_at',)
    autocomplete_fields = ('member', 'association')

    def get_list_filter(self, request):
        list_filter = super().get_list_filter(request) or tuple()
        if self.is_association_admin(request):
            return (f for f in list_filter if f != "association")
        return list_filter

    def get_exclude(self, request, obj = None):
        excluded_fields = super().get_exclude(request, obj) or tuple()
        if request.user.is_superuser:
            return excluded_fields
        if self.is_association_admin(request):
            excluded_fields += ("association",)
            return excluded_fields
        return excluded_fields


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self.is_superuser(request):
            return qs
        if assoc_admin := self.is_association_admin(request):
            return qs.filter(association=assoc_admin.association)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.association = request.user.association_admin.association
        super().save_model(request, obj, form, change)

class CabinetMemberInline(admin.TabularInline):
    model = CabinetMember
    extra = 1
    verbose_name = 'Cabinet Member'
    verbose_name_plural = 'Cabinet Members'

@admin.register(Cabinet)
class CabinetAdmin(admin.ModelAdmin, CheckUserIdentityMixin):
    inlines = [CabinetMemberInline]
    list_display = ('association', 'year')
    search_fields = ("year", )

    def get_exclude(self, request, obj = None):
        excluded_fields = super().get_exclude(request, obj) or tuple()
        if request.user.is_superuser:
            return excluded_fields
        if hasattr(request.user, "association_admin"):
            excluded_fields += ("association",)
            return excluded_fields
        return excluded_fields

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if assoc_admin := self.is_association_admin(request):
            return qs.filter(association=assoc_admin.association)
        return qs.none()
    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.association = request.user.association_admin.association
        super().save_model(request, obj, form, change)
class AssociationListFilter(admin.SimpleListFilter, CheckUserIdentityMixin):
    title = "Association"

    # Parameter for the filter that will be used in the URL query.
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


class CabinetListFilter(admin.SimpleListFilter, CheckUserIdentityMixin):
    title = "Cabinet"

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "cabinet"

    def lookups(self, request, model_admin):
        if self.is_association_admin(request):
            assoc = request.user.association_admin.association
            cabinets = Cabinet.objects.filter(association=assoc)
            return [(cabinet.id, cabinet.year) for cabinet in cabinets]
        return []
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(cabinet__id=self.value())
        return queryset

@admin.register(CabinetMember)
class CabinetMemberAdmin(admin.ModelAdmin, CheckUserIdentityMixin):
    list_display = ('cabinet', 'member', 'role')
    # search_fields = ('member__full_name', 'cabinet__association__name')
    list_filter = (CabinetListFilter, 'role')
    ordering = ('-cabinet__year', 'role')
    autocomplete_fields = ('member', 'cabinet')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if assoc_admin := self.is_association_admin(request):
            return qs.filter(cabinet__association=assoc_admin.association)
        return qs.none()
    
@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin, CheckUserIdentityMixin):
    list_display = ('association', 'fee_type', 'amount', 'duration_months', 'created_at')
    # search_fields = ('association__name',)
    list_filter = ('fee_type', AssociationListFilter)
    ordering = ('-created_at',)

    def get_exclude(self, request, obj = None):
        excluded_fields = super().get_exclude(request, obj) or tuple()
        if request.user.is_superuser:
            return excluded_fields
        if self.is_association_admin(request):
            excluded_fields += ("association",)
            return excluded_fields
        return excluded_fields

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if assoc_admin := self.is_association_admin(request):
            return qs.filter(association=assoc_admin.association)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.association = request.user.association_admin.association
        super().save_model(request, obj, form, change)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin, CheckUserIdentityMixin):
    list_display = ('membership', 'payment_date', 'fee','amount_paid', 'status')
    # search_fields = ('member__full_name',)
    list_filter = ('payment_date',)
    ordering = ('-payment_date',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "membership" and not request.user.is_superuser:
            if assoc_admin := self.is_association_admin(request):
                assoc = assoc_admin.association
                kwargs["queryset"] = Membership.objects.filter(association=assoc)
        if db_field.name == "fee" and not request.user.is_superuser:
            if assoc_admin := self.is_association_admin(request):
                assoc = assoc_admin.association
                kwargs["queryset"] = Fee.objects.filter(association=assoc)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin:
            return qs.filter(membership__association=assoc_admin.association)
        return qs.none()

    
@admin.register(Event)
class EventAdmin(admin.ModelAdmin, CheckUserIdentityMixin):
    list_display = ('title', 'association', 'event_date', 'created_at', 'description','venue','posted_by')
    search_fields = ('name',)
    list_filter = (AssociationListFilter, 'event_date')
    ordering = ('-created_at',)

    def get_exclude(self, request, obj = None):
        excluded_fields = super().get_exclude(request, obj) or tuple()
        if request.user.is_superuser:
            return excluded_fields
        if self.is_association_admin(request):
            excluded_fields += ("association",)
            return excluded_fields
        return excluded_fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "posted_by" and not request.user.is_superuser:
            if assoc_admin := self.is_association_admin(request):
                assoc = assoc_admin.association
                kwargs["queryset"] = Membership.objects.filter(association=assoc)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if assoc_admin := self.is_association_admin(request):
            return qs.filter(association=assoc_admin.association)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.association = request.user.association_admin.association
        super().save_model(request, obj, form, change)

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin, CheckUserIdentityMixin):
    list_display = ('member', 'association', 'subject', 'message', 'submitted_at')
    search_fields = ('member', 'message')
    list_filter = ('association', 'submitted_at')
    ordering = ('-submitted_at',)

    def get_exclude(self, request, obj = None):
        excluded_fields = super().get_exclude(request, obj) or tuple()
        if request.user.is_superuser:
            return excluded_fields
        if self.is_association_admin(request):
            excluded_fields += ("association",)
            return excluded_fields
        return excluded_fields

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if assoc_admin := self.is_association_admin(request):
            return qs.filter(association=assoc_admin.association)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.association = request.user.association_admin.association
        super().save_model(request, obj, form, change)
