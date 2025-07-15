from django.contrib import admin
from campus_nexus.models import Faculty, Course, Association, Member, Cabinet, Payment, Event, Fee, Membership, CabinetMember

@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    ordering = ('-created_at',)

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_years', 'faculty', 'created_at')
    search_fields = ('name',)
    list_filter = ('faculty',)
    ordering = ('-created_at',)

@admin.register(Association)
class AssociationAdmin(admin.ModelAdmin):
    list_display = ('name', 'faculty', 'created_at', 'description',)
    search_fields = ('name',)
    list_filter = ('faculty',)
    ordering = ('-created_at',)

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'member_type', 'faculty', 'course', 'created_at',)
    search_fields = ('full_name', 'email')
    list_filter = ('member_type', 'faculty', 'course')
    ordering = ('-created_at',)

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('member', 'association', 'joined_at', 'status')
    search_fields = ('member__full_name', 'association__name')
    list_filter = ('association', 'status')
    ordering = ('-joined_at',)
    raw_id_fields = ('member', 'association')

class CabinetMemberInline(admin.TabularInline):
    model = CabinetMember
    extra = 1
    verbose_name = 'Cabinet Member'
    verbose_name_plural = 'Cabinet Members'

@admin.register(Cabinet)
class CabinetAdmin(admin.ModelAdmin):
    inlines = [CabinetMemberInline]
    list_display = ('association', 'year')

@admin.register(CabinetMember)
class CabinetMemberAdmin(admin.ModelAdmin):
    list_display = ('cabinet', 'member', 'role')
    search_fields = ('member__full_name', 'cabinet__association__name')
    list_filter = ('cabinet', 'role')
    ordering = ('-cabinet__year', 'role')
    raw_id_fields = ('member', 'cabinet')

@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ('association', 'fee_type', 'amount', 'duration_months', 'created_at')
    search_fields = ('association__name',)
    list_filter = ('fee_type', 'association')
    ordering = ('-created_at',)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('membership', 'payment_date', 'fee','amount_paid', 'status')
    search_fields = ('member__full_name',)
    list_filter = ('payment_date',)
    ordering = ('-payment_date',)

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'association', 'event_date', 'created_at', 'description','venue','posted_by')
    search_fields = ('name',)
    list_filter = ('association', 'event_date')
    ordering = ('-created_at',)
