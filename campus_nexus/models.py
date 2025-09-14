from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()


class Faculty(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
      verbose_name_plural = 'Faculties'

    def __str__(self):
        return self.name


class Course(models.Model):
    name = models.CharField(max_length=100)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='courses')
    duration_years = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class AssociationAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='association_admin', limit_choices_to={'is_staff': True, 'is_superuser': False})
    association = models.ForeignKey('Association', on_delete=models.CASCADE, related_name='admins')

    def clean(self):
        if self.user and self.user.is_superuser:
            raise ValidationError("Superusers cannot be assigned as Association Admins.")

        # Require staff=True so they can log in to admin
        if self.user and not self.user.is_staff:
            raise ValidationError("Association Admins must have is_staff=True to access the admin site.")

    def __str__(self):
        return f"{self.user.username} - {self.association.name}"

class Association(models.Model):
    name = models.CharField(max_length=100)
    faculty = models.ForeignKey(Faculty, on_delete=models.SET_NULL, null=True, blank=True, related_name='associations')
    description = models.TextField(blank=True)
    logo_image = models.ImageField(upload_to='associations/logos/', blank=True, null=True)
    theme_color = models.CharField(max_length=20, default="#0d6efd")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Member(models.Model):
    MEMBER_TYPES = [
        ('student', 'Student'),
        ('alumni', 'Alumni'),
        ('external', 'External'),
    ]

    first_name = models.CharField(max_length=50, default='')
    last_name = models.CharField(max_length=50, default='')
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, validators=[RegexValidator(r'^\+?\d{9,15}$')])

    registration_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    national_id_number = models.CharField(max_length=20, unique=True, null=True, blank=True)

    member_type = models.CharField(max_length=10, choices=MEMBER_TYPES)
    faculty = models.ForeignKey(Faculty, on_delete=models.SET_NULL, null=True, blank=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.member_type in ['student', 'alumni'] and not self.registration_number:
            raise ValidationError("Registration number is required for students and alumni.")
        if self.member_type == 'external' and not self.national_id_number:
            raise ValidationError("National ID number (NIN) is required for external members.")

    def __str__(self):
        return self.full_name


class Membership(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='memberships')
    association = models.ForeignKey(Association, on_delete=models.CASCADE, related_name='memberships')
    joined_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    def __str__(self):
        return f"{self.member.full_name} → {self.association.name}"


class Cabinet(models.Model):
   association = models.OneToOneField(Association, on_delete=models.CASCADE, related_name='cabinets')
   year = models.CharField(max_length=10)

   def __str__(self):
       return f"{self.association.name} Cabinet ({self.year})"

class CabinetMember(models.Model):
    cabinet = models.ForeignKey(Cabinet, on_delete=models.CASCADE, related_name='cabinet_members')
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    role = models.CharField(max_length=50)

    class Meta:
        unique_together = ('cabinet', 'role')

    def __str__(self):
        return f"{self.role} - {self.member.full_name}"


class Fee(models.Model):
    FEE_TYPE_CHOICES = [
        ('membership', 'Membership'),
        ('subscription', 'Subscription'),
    ]

    association = models.ForeignKey(Association, on_delete=models.CASCADE, related_name='fees')
    fee_type = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    duration_months = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.fee_type} - {self.amount}"


class Payment(models.Model):
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name='payments')
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=50)
    receipt_image = models.ImageField(upload_to='payments/receipts/', null=True, blank=True)
    status = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.membership.member.full_name} - {self.amount_paid}"


class Event(models.Model):
    association = models.ForeignKey(Association, on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=200)
    description = models.TextField()
    event_date = models.DateTimeField()
    venue = models.CharField(max_length=150)
    posted_by = models.ForeignKey(Membership, on_delete=models.SET_NULL, null=True, related_name='posted_events')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
