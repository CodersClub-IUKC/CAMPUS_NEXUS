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
    AssociationAdmin
)

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
class AssociationAdmin(admin.ModelAdmin):
    list_display = ('name', 'faculty', 'created_at', 'description',)
    # search_fields = ('name',)
    list_filter = ('faculty',)
    ordering = ('-created_at',)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'member_type', 'faculty', 'course', 'created_at',)
    # search_fields = ('full_name', 'email')
    list_filter = ('member_type', 'faculty', 'course')
    ordering = ('-created_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin:
            return qs.filter(memberships__association=assoc_admin.association).distinct()
        return qs.none()
    

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('member', 'association', 'joined_at', 'status')
    # search_fields = ('member__full_name', 'association__name')
    list_filter = ('association', 'status')
    ordering = ('-joined_at',)
    raw_id_fields = ('member', 'association')

    def get_list_filter(self, request):
        list_filter = super().get_list_filter(request) or tuple()
        if hasattr(request.user, "association_admin"):
            return (f for f in list_filter if f != "association")
        return list_filter
    
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
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin:
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
class CabinetAdmin(admin.ModelAdmin):
    inlines = [CabinetMemberInline]
    list_display = ('association', 'year')

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
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin:
            return qs.filter(association=assoc_admin.association)
        return qs.none()

@admin.register(CabinetMember)
class CabinetMemberAdmin(admin.ModelAdmin):
    list_display = ('cabinet', 'member', 'role')
    # search_fields = ('member__full_name', 'cabinet__association__name')
    list_filter = ('cabinet', 'role')
    ordering = ('-cabinet__year', 'role')
    raw_id_fields = ('member', 'cabinet')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin:
            return qs.filter(cabinet__association=assoc_admin.association)
        return qs.none()

@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ('association', 'fee_type', 'amount', 'duration_months', 'created_at')
    # search_fields = ('association__name',)
    list_filter = ('fee_type', 'association')
    ordering = ('-created_at',)

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
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin:
            return qs.filter(association=assoc_admin.association)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.association = request.user.association_admin.association
        super().save_model(request, obj, form, change)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('membership', 'payment_date', 'fee','amount_paid', 'status')
    # search_fields = ('member__full_name',)
    list_filter = ('payment_date',)
    ordering = ('-payment_date',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "membership" and not request.user.is_superuser:
            if hasattr(request.user, "association_admin"):
                assoc = request.user.association_admin.association
                kwargs["queryset"] = Membership.objects.filter(association=assoc)
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
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'association', 'event_date', 'created_at', 'description','venue','posted_by')
    # search_fields = ('name',)
    list_filter = ('association', 'event_date')
    ordering = ('-created_at',)

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
        assoc_admin = getattr(request.user, "association_admin", None)
        if assoc_admin:
            return qs.filter(association=assoc_admin.association)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.association = request.user.association_admin.association
        super().save_model(request, obj, form, change)
