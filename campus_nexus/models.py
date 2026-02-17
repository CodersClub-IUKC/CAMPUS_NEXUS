from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.files.base import ContentFile
from django.conf import settings
try:
    from .theme_utils import get_association_theme
except Exception:
    def get_association_theme(association):
        
        name = getattr(association, "name", "association")
        # Minimal default CSS; adjust as needed.
        return "/* default theme for {} */\n:root {{ --association-name: \"{}\"; }}\n".format(name, name)


User = get_user_model()


class Faculty(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
      verbose_name_plural = 'Faculties'

    def __str__(self):
        return self.name

class Dean(models.Model):
    """
    Represents the Dean of Students (read-only stakeholder role).

    We keep this as a OneToOne model to the Django user so that:
    - authentication stays in Django admin,
    - authorization is determined by the presence of user.dean,
    - we avoid relying on fragile username/group checks.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="dean",
        limit_choices_to={"is_staff": True, "is_superuser": False},
    )

    def clean(self):
        if self.user and self.user.is_superuser:
            raise ValidationError("Superusers cannot be assigned as Deans.")
        if self.user and not self.user.is_staff:
            raise ValidationError("Deans must have is_staff=True to access the admin site.")

    def __str__(self):
        return f"{self.user.username}"

class Guild(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='guild', limit_choices_to={'is_staff': True, 'is_superuser': False})

    def clean(self):
        if self.user and self.user.is_superuser:
            raise ValidationError("Superusers cannot be assigned as Guilds.")

        # Require staff=True so they can log in to admin
        if self.user and not self.user.is_staff:
            raise ValidationError("Guilds must have is_staff=True to access the admin site.")

    def __str__(self):
        return f"{self.user.username}"


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
    profile_photo = models.ImageField(upload_to="associations/presidents/", blank=True, null=True)
    title = models.CharField(max_length=80, blank=True, default="Association Admin")
    bio = models.TextField(blank=True, default="")

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
    theme_css_file = models.FileField(upload_to="associations/themes/", blank=True, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    from django.core.files.base import ContentFile

    def save(self, *args, **kwargs):
        # Detect logo change
        if self.pk:
            assoc = Association.objects.filter(pk=self.pk).only("logo_image").first()
            logo_changed = assoc and assoc.logo_image != self.logo_image
        else:
            logo_changed = bool(self.logo_image)

        # Save first to ensure logo has a real file path
        super().save(*args, **kwargs)

        # If logo added/changed, regenerate CSS (best-effort, never crash)
        if logo_changed and self.logo_image:
            css_content = get_association_theme(self)  # may be str or None

            # Only save when we got valid CSS text
            if isinstance(css_content, str) and css_content.strip():
                self.theme_css_file.save(
                    f"association_{self.id}.css",
                    ContentFile(css_content.encode("utf-8")),
                    save=False,
                )
                super().save(update_fields=["theme_css_file"])
            # else: do nothing (keep previous theme_css_file)


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
    
    registration_number = models.CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)
    national_id_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_members')
    created_in_association = models.ForeignKey(Association, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_members')
    nationality = models.CharField(max_length=50, blank=True)
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
        return f"{self.full_name} ({self.registration_number})"  
  
  
class Membership(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='memberships')
    association = models.ForeignKey(Association, on_delete=models.CASCADE, related_name='memberships')
    joined_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["member", "association"],
                name="unique_member_per_association",
            )
        ]
        
    from django.core.exceptions import ValidationError

    def clean(self):
        super().clean()

        # Guard: during admin add, association might not yet be attached
        if not self.association_id:
            # If you want to allow admin form to set it later, do NOT raise here.
            # But for safety + correctness, it's better to raise a validation error.
            raise ValidationError({"association": "Association is required."})

        # Only enforce rule for faculty-based associations
        assoc = self.association
        if not assoc.faculty_id:
            return

        existing = (
            Membership.objects
            .filter(member=self.member, association__faculty__isnull=False)
            .exclude(pk=self.pk)
            .select_related("association__faculty")
        )

        # If member already has a faculty-based membership with a different faculty, block it
        for m in existing:
            if m.association.faculty_id != assoc.faculty_id:
                raise ValidationError({
                    "association": (
                        "This student is already in a faculty-based association "
                        f"({m.association.name} - {m.association.faculty.name}). "
                        "They cannot join another faculty-based association under a different faculty."
                    )
                })


    def __str__(self):
        return f"{self.member.full_name} → {self.association.name}"

class Cabinet(models.Model):
   association = models.ForeignKey(Association, on_delete=models.CASCADE, related_name='cabinets')
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

class Charge(models.Model):
    PURPOSE_CHOICES = [
        ("membership_fee", "Membership Fee"),
        ("subscription_fee", "Subscription Fee"),
        ("event", "Event / Dinner"),
        ("merch", "Merchandise"),
        ("donation", "Donation"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("partial", "Partial"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ]

    association = models.ForeignKey(Association, on_delete=models.CASCADE, related_name="charges")
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="charges")

    # Optional link to your Fee (for dues)
    fee = models.ForeignKey(Fee, on_delete=models.SET_NULL, null=True, blank=True, related_name="charges")

    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default="other")
    title = models.CharField(max_length=200, blank=True, default="")
    description = models.TextField(blank=True, default="")

    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unpaid")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_charges")
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Ensure membership matches association
        if self.membership_id and self.association_id:
            if self.membership.association_id != self.association_id:
                raise ValidationError({"membership": "Membership must belong to the selected association."})

        # Fee must belong to the same association
        if self.fee_id and self.association_id:
            if self.fee.association_id != self.association_id:
                raise ValidationError({"fee": "Fee must belong to the selected association."})

        if self.amount_due is not None and self.amount_due <= 0:
            raise ValidationError({"amount_due": "Amount due must be greater than 0."})

    @property
    def amount_paid_total(self):
        return self.payments.aggregate(s=models.Sum("amount_paid")).get("s") or 0

    def recompute_status(self):
        if self.status == "cancelled":
            return
        paid = self.amount_paid_total
        if paid <= 0:
            self.status = "unpaid"
        elif paid < self.amount_due:
            self.status = "partial"
        else:
            self.status = "paid"

    def __str__(self):
        label = self.title or self.get_purpose_display()
        return f"{self.membership.member.full_name} • {label} • {self.amount_due}"
class Payment(models.Model):
    STATUS_CHOICES = [
        ("recorded", "Recorded"),
        ("reversed", "Reversed"),
    ]

    METHOD_CHOICES = [
        ("cash", "Cash"),
        ("momo", "Mobile Money"),
        ("bank", "Bank"),
        ("other", "Other"),
    ]

    charge = models.ForeignKey(Charge, on_delete=models.CASCADE, related_name="payments")
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="payments")

    # Optional: keep fee for backward compatibility / reporting
    fee = models.ForeignKey(Fee, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")

    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField(default=timezone.now)   # when member paid
    recorded_at = models.DateTimeField(auto_now_add=True)  # when treasurer recorded
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="recorded_payments")

    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="cash")
    reference_code = models.CharField(max_length=120, blank=True, default="")  # momo txn, bank slip no.
    receipt_image = models.ImageField(upload_to="payments/receipts/", null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="recorded")
    note = models.TextField(blank=True, default="")

    def clean(self):
        super().clean()

        # Ensure membership belongs to charge association and matches charge membership
        if self.charge_id:
            if self.membership_id and self.charge.membership_id != self.membership_id:
                raise ValidationError({"membership": "Membership must match the charge membership."})

            if self.membership_id and self.membership.association_id != self.charge.association_id:
                raise ValidationError({"membership": "Membership must belong to the same association as the charge."})

            # Fee sanity
            if self.fee_id and self.charge.fee_id and self.fee_id != self.charge.fee_id:
                raise ValidationError({"fee": "Fee must match the charge fee."})

        if self.amount_paid is not None and self.amount_paid <= 0:
            raise ValidationError({"amount_paid": "Amount paid must be greater than 0."})

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

class Feedback(models.Model):
    association = models.ForeignKey(
        Association, on_delete=models.SET_NULL, null=True, blank=True, related_name="feedbacks"
    )
    member = models.ForeignKey(
        Member, on_delete=models.SET_NULL, null=True, blank=True, related_name="feedbacks"
    )

    subject = models.CharField(max_length=200)
    message = models.TextField()

    submitted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_feedbacks"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-submitted_at",)

    def __str__(self):
        who = self.member.full_name if self.member else (self.submitted_by.username if self.submitted_by else "Unknown")
        return f"Feedback from {who} - {self.subject}"

from django.db import models
from django.core.exceptions import ValidationError

class GuildCabinet(models.Model):
    year = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-year",)

    def __str__(self):
        return f"Guild Cabinet ({self.year})"


class GuildExecutive(models.Model):
    POSITION_CHOICES = [
        ("guild_president", "Guild President"),
        ("lady_vice", "Lady Vice President"),
        ("vice_lady_vice", "Vice Lady Vice President"),
        ("prime_minister", "Prime Minister"),
        ("minister", "Minister"),
        ("state_minister", "State Minister (Deputy)"),
    ]

    cabinet = models.ForeignKey(GuildCabinet, on_delete=models.CASCADE, related_name="executives")
    member = models.ForeignKey("Member", on_delete=models.CASCADE, related_name="guild_executive_roles")

    position_type = models.CharField(max_length=30, choices=POSITION_CHOICES)

    # Ministers / State Ministers
    ministry = models.CharField(max_length=120, blank=True, default="")

    # State minister reports to a minister
    reports_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deputies",
        limit_choices_to={"position_type": "minister"},
    )

    # Photo only for executives
    photo = models.ImageField(upload_to="guild/executives/", blank=True, null=True)

    # stable ordering everywhere
    sort_order = models.PositiveIntegerField(default=1000, db_index=True)

    appointed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "ministry", "member__first_name")

    def clean(self):
        # Ministry required for ministers and deputies
        if self.position_type in ["minister", "state_minister"] and not self.ministry:
            raise ValidationError({"ministry": "Ministry is required for Ministers and State Ministers."})

        if self.position_type not in ["minister", "state_minister"] and self.ministry:
            raise ValidationError({"ministry": "Only Ministers/State Ministers can have a ministry."})

        # Deputy must have reports_to
        if self.position_type == "state_minister" and not self.reports_to_id:
            raise ValidationError({"reports_to": "State Minister must be assigned to a Minister (reports_to)."})

        if self.position_type != "state_minister" and self.reports_to_id:
            raise ValidationError({"reports_to": "Only State Ministers can have reports_to."})

        # Ensure reports_to is in same cabinet
        if self.position_type == "state_minister" and self.reports_to_id:
            if self.reports_to.cabinet_id != self.cabinet_id:
                raise ValidationError({"reports_to": "reports_to must be a Minister in the same cabinet year."})

    def save(self, *args, **kwargs):
        ranks = {
            "guild_president": 10,
            "lady_vice": 20,
            "vice_lady_vice": 30,
            "prime_minister": 40,
            "minister": 100,
            "state_minister": 200,
        }
        self.sort_order = ranks.get(self.position_type, 1000)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.position_type in ["minister", "state_minister"]:
            return f"{self.get_position_type_display()} of {self.ministry} - {self.member.full_name}"
        return f"{self.get_position_type_display()} - {self.member.full_name}"



class GuildAnnouncement(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    cabinet = models.ForeignKey(GuildCabinet, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=True)
    posted_by = models.ForeignKey(
        GuildExecutive, on_delete=models.SET_NULL, null=True, blank=True, related_name="announcements"
    )

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title

