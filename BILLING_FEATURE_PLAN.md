# Selectable Billing Feature - Implementation Plan

## Overview
This feature enables Association Admins and Super Users to:
1. Create billable items (templates for charges)
2. Create bills from billable items
3. Attach bills to selective members or all members
4. Track member balances for each bill

---

## Phase 1: Data Models

### 1.1 BillableItem Model
A template/configuration for creating charges.

```python
class BillableItem(models.Model):
    association = ForeignKey(Association, on_delete=CASCADE)
    name = CharField(max_length=200)
    description = TextField(blank=True)
    amount = DecimalField(max_digits=12, decimal_places=2)
    
    # Optional: Category/purpose
    category = CharField(choices=CATEGORY_CHOICES)  # event, merchandise, fee, etc.
    
    # Recurrence settings (for future enhancements)
    is_recurring = BooleanField(default=False)
    recurrence_type = CharField(choices=[('one-time', 'One-Time'), ('monthly', 'Monthly'), ('yearly', 'Yearly')], null=True, blank=True)
    
    created_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    is_active = BooleanField(default=True)
    
    class Meta:
        unique_together = ('association', 'name')  # Prevent duplicate names per association
    
    def __str__(self):
        return f"{self.association.name} - {self.name}"
```

### 1.2 Bill Model
Individual bill instance created from BillableItems for specific members.

```python
class Bill(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
    ]
    
    ATTACHMENT_TYPE_CHOICES = [
        ('selective', 'Selective Members'),
        ('all', 'All Members'),
    ]
    
    association = ForeignKey(Association, on_delete=CASCADE)
    billable_item = ForeignKey(BillableItem, on_delete=PROTECT)  # Keep history
    
    title = CharField(max_length=200)  # Override from BillableItem if needed
    description = TextField(blank=True)
    
    # When to collect
    due_date = DateField(null=True, blank=True)
    issue_date = DateField(auto_now_add=True)
    
    # Who gets billed
    attachment_type = CharField(max_length=20, choices=ATTACHMENT_TYPE_CHOICES)
    # If selective: members linked via BillMembership
    # If all: auto-expand to all active members during attachment
    
    amount = DecimalField(max_digits=12, decimal_places=2)  # Amount per member
    
    status = CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    created_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Bill: {self.title} - {self.association.name}"
    
    @property
    def total_members_billed(self):
        return self.memberships.count()
    
    @property
    def total_amount_due(self):
        return self.amount * self.total_members_billed
    
    @property
    def total_amount_collected(self):
        # Sum of all charges for this bill that are paid
        from django.db.models import Sum
        return self.charges.filter(status='paid').aggregate(
            total=Sum('amount_paid_total')
        )['total'] or 0
```

### 1.3 BillMembership Model
Join table linking bills to specific members (for selective billing).

```python
class BillMembership(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('waived', 'Waived'),
        ('cancelled', 'Cancelled'),
    ]
    
    bill = ForeignKey(Bill, on_delete=CASCADE, related_name='memberships')
    membership = ForeignKey(Membership, on_delete=CASCADE, related_name='bills')
    
    amount_due = DecimalField(max_digits=12, decimal_places=2)
    status = CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    
    # Tracking
    assigned_at = DateTimeField(auto_now_add=True)
    paid_at = DateTimeField(null=True, blank=True)  # When fully paid
    waived_at = DateTimeField(null=True, blank=True)
    waived_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='waived_bills')
    waive_reason = TextField(blank=True)
    
    class Meta:
        unique_together = ('bill', 'membership')
    
    def __str__(self):
        return f"{self.membership.member.full_name} - {self.bill.title}"
    
    @property
    def balance(self):
        """Calculate remaining balance"""
        paid = self.amount_paid_total
        remaining = self.amount_due - paid
        return max(0, remaining)
    
    @property
    def amount_paid_total(self):
        """Get total paid through Charge entries"""
        from django.db.models import Sum
        return self.charges.aggregate(
            total=models.Sum('payments__amount_paid')
        )['total'] or 0
    
    def update_status(self):
        """Auto-update status based on payment"""
        if self.status == 'waived' or self.status == 'cancelled':
            return
        
        paid = self.amount_paid_total
        if paid <= 0:
            self.status = 'unpaid'
        elif paid < self.amount_due:
            self.status = 'partial'
        else:
            self.status = 'paid'
            self.paid_at = timezone.now()
        self.save()
```

### 1.4 Link to Existing Charge Model
Modify `Charge` model to reference BillMembership:

```python
class Charge(models.Model):
    # ... existing fields ...
    
    # New field to link to BillMembership
    bill_membership = ForeignKey(
        'BillMembership', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='charges'
    )
    
    # Keep existing fee for backward compatibility
    fee = ForeignKey(Fee, on_delete=models.SET_NULL, null=True, blank=True, related_name="charges")
```

---

## Phase 2: Permissions & Authorization

### 2.1 Custom Permission Classes

```python
# campus_nexus/permissions.py

class IsAssociationAdminOrSuperUser(BasePermission):
    """
    Allow access to association admins of the specific association
    or superusers.
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # obj can be Association, Bill, BillableItem, etc.
        if request.user.is_superuser:
            return True
        
        # Check if user is admin of this association
        try:
            admin = request.user.association_admin
            return admin.association_id == obj.association_id
        except:
            return False

class IsBillAdmin(BasePermission):
    """Can only view/edit bills for their association"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or 
            hasattr(request.user, 'association_admin')
        )
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        
        try:
            admin = request.user.association_admin
            return admin.association_id == obj.association_id
        except:
            return False
```

### 2.2 Permission Rules

| Action | Super User | Association Admin | Regular Member |
|--------|-----------|-------------------|-----------------|
| Create BillableItem | ✓ | ✓ (own assoc only) | ✗ |
| Edit BillableItem | ✓ | ✓ (own assoc only) | ✗ |
| List BillableItems | ✓ | ✓ (own assoc only) | ✗ |
| Create Bill | ✓ | ✓ (own assoc only) | ✗ |
| Attach Bill to Members | ✓ | ✓ (own assoc only) | ✗ |
| View Bill Details | ✓ | ✓ (own assoc only) | ✗ |
| View Member Balances | ✓ | ✓ (own assoc only) | ✗ |
| Record Payment | ✓ | ✓ (own assoc only) | ✗ |
| Waive Bill | ✓ | ✓ (own assoc only) | ✗ |
| View Own Bills | All | All | ✓ |

---

## Phase 3: API Endpoints

### 3.1 BillableItem Endpoints

```
POST   /api/associations/{id}/billable-items/        # Create
GET    /api/associations/{id}/billable-items/        # List
GET    /api/billable-items/{id}/                     # Retrieve
PUT    /api/billable-items/{id}/                     # Update
DELETE /api/billable-items/{id}/                     # Delete
```

### 3.2 Bill Endpoints

```
POST   /api/associations/{id}/bills/                 # Create
GET    /api/associations/{id}/bills/                 # List
GET    /api/bills/{id}/                              # Retrieve
PUT    /api/bills/{id}/                              # Update
DELETE /api/bills/{id}/                              # Delete (only draft)
POST   /api/bills/{id}/activate/                     # Activate bill
POST   /api/bills/{id}/cancel/                       # Cancel bill
```

### 3.3 Bill Attachment Endpoints

```
POST   /api/bills/{id}/attach-members/               # Attach to selective members
POST   /api/bills/{id}/attach-all-members/           # Attach to all active members
GET    /api/bills/{id}/memberships/                  # List attached members
GET    /api/bills/{id}/memberships/{member_id}/     # Get member balance
POST   /api/bills/{id}/memberships/{member_id}/waive/  # Waive bill
```

### 3.4 Balance Tracking Endpoints

```
GET    /api/associations/{id}/billing-dashboard/    # Overall stats
GET    /api/bills/{id}/balance-summary/              # Bill payment summary
GET    /api/members/{id}/bill-history/               # Member's bill history
GET    /api/members/{id}/balance/                    # Member's current balance
```

---

## Phase 4: Serializers

### 4.1 BillableItemSerializer

```python
class BillableItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillableItem
        fields = [
            'id', 'association', 'name', 'description', 'amount',
            'category', 'is_recurring', 'recurrence_type',
            'created_by', 'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
```

### 4.2 BillMembershipSerializer

```python
class BillMembershipSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='membership.member.full_name', read_only=True)
    amount_paid = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    
    class Meta:
        model = BillMembership
        fields = [
            'id', 'membership', 'member_name', 'amount_due', 'amount_paid',
            'balance', 'status', 'assigned_at', 'paid_at', 'waived_at'
        ]
        read_only_fields = ['id', 'assigned_at', 'paid_at']
    
    def get_amount_paid(self, obj):
        return obj.amount_paid_total
    
    def get_balance(self, obj):
        return obj.balance
```

### 4.3 BillSerializer

```python
class BillSerializer(serializers.ModelSerializer):
    memberships = BillMembershipSerializer(many=True, read_only=True)
    total_amount_due = serializers.SerializerMethodField()
    total_amount_collected = serializers.SerializerMethodField()
    total_members_billed = serializers.SerializerMethodField()
    
    class Meta:
        model = Bill
        fields = [
            'id', 'association', 'billable_item', 'title', 'description',
            'due_date', 'issue_date', 'attachment_type', 'amount',
            'status', 'created_by', 'created_at', 'updated_at',
            'memberships', 'total_amount_due', 'total_amount_collected',
            'total_members_billed'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_total_amount_due(self, obj):
        return obj.total_amount_due
    
    def get_total_amount_collected(self, obj):
        return obj.total_amount_collected
    
    def get_total_members_billed(self, obj):
        return obj.total_members_billed
```

---

## Phase 5: Views/ViewSets

### 5.1 BillableItemViewSet

```python
class BillableItemViewSet(viewsets.ModelViewSet):
    serializer_class = BillableItemSerializer
    permission_classes = [IsAuthenticated, IsBillAdmin]
    
    def get_queryset(self):
        association_id = self.kwargs.get('association_id')
        queryset = BillableItem.objects.filter(association_id=association_id)
        
        if not self.request.user.is_superuser:
            # Verify user is admin of this association
            if not self.request.user.association_admin.association_id == association_id:
                return BillableItem.objects.none()
        
        return queryset
    
    def perform_create(self, serializer):
        association_id = self.kwargs.get('association_id')
        serializer.save(
            association_id=association_id,
            created_by=self.request.user
        )
```

### 5.2 BillViewSet

```python
class BillViewSet(viewsets.ModelViewSet):
    serializer_class = BillSerializer
    permission_classes = [IsAuthenticated, IsBillAdmin]
    
    def get_queryset(self):
        association_id = self.kwargs.get('association_id')
        queryset = Bill.objects.filter(association_id=association_id)
        
        if not self.request.user.is_superuser:
            if not self.request.user.association_admin.association_id == association_id:
                return Bill.objects.none()
        
        return queryset
    
    def perform_create(self, serializer):
        association_id = self.kwargs.get('association_id')
        serializer.save(
            association_id=association_id,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        bill = self.get_object()
        if bill.status != 'draft':
            return Response(
                {'error': 'Only draft bills can be activated'},
                status=status.HTTP_400_BAD_REQUEST
            )
        bill.status = 'active'
        bill.save()
        return Response(self.get_serializer(bill).data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        bill = self.get_object()
        bill.status = 'cancelled'
        bill.save()
        return Response(self.get_serializer(bill).data)
    
    @action(detail=True, methods=['post'])
    def attach_members(self, request, pk=None):
        """Attach bill to selective members"""
        bill = self.get_object()
        member_ids = request.data.get('member_ids', [])
        
        memberships = Membership.objects.filter(
            id__in=member_ids,
            association_id=bill.association_id
        )
        
        for membership in memberships:
            BillMembership.objects.get_or_create(
                bill=bill,
                membership=membership,
                defaults={'amount_due': bill.amount}
            )
        
        return Response({
            'success': True,
            'attached_count': memberships.count()
        })
    
    @action(detail=True, methods=['post'])
    def attach_all_members(self, request, pk=None):
        """Attach bill to all active members"""
        bill = self.get_object()
        
        active_memberships = Membership.objects.filter(
            association_id=bill.association_id,
            status='active'
        )
        
        for membership in active_memberships:
            BillMembership.objects.get_or_create(
                bill=bill,
                membership=membership,
                defaults={'amount_due': bill.amount}
            )
        
        return Response({
            'success': True,
            'attached_count': active_memberships.count()
        })
```

### 5.3 BillMembershipViewSet

```python
class BillMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = BillMembershipSerializer
    permission_classes = [IsAuthenticated, IsBillAdmin]
    
    def get_queryset(self):
        bill_id = self.kwargs.get('bill_id')
        bill = Bill.objects.get(id=bill_id)
        
        # Check permission
        if not self.request.user.is_superuser:
            if not self.request.user.association_admin.association_id == bill.association_id:
                return BillMembership.objects.none()
        
        return BillMembership.objects.filter(bill_id=bill_id)
    
    @action(detail=True, methods=['post'])
    def waive(self, request, pk=None):
        """Waive a member's bill"""
        bill_membership = self.get_object()
        reason = request.data.get('reason', '')
        
        bill_membership.status = 'waived'
        bill_membership.waived_at = timezone.now()
        bill_membership.waived_by = request.user
        bill_membership.waive_reason = reason
        bill_membership.save()
        
        return Response(self.get_serializer(bill_membership).data)
```

---

## Phase 6: Business Logic

### 6.1 Signals for Auto-Status Updates

```python
# campus_nexus/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Payment, BillMembership

@receiver(post_save, sender=Payment)
def update_bill_membership_on_payment(sender, instance, created, **kwargs):
    """Update BillMembership status when payment recorded"""
    if instance.charge and instance.charge.bill_membership:
        instance.charge.bill_membership.update_status()
```

### 6.2 Service Layer for Complex Operations

```python
# campus_nexus/services/billing_service.py

class BillingService:
    @staticmethod
    def create_bill_from_item(billable_item, title=None, due_date=None, user=None):
        """Create bill from billable item template"""
        bill = Bill.objects.create(
            association=billable_item.association,
            billable_item=billable_item,
            title=title or billable_item.name,
            description=billable_item.description,
            amount=billable_item.amount,
            due_date=due_date,
            created_by=user,
            status='draft'
        )
        return bill
    
    @staticmethod
    def get_member_billing_summary(membership):
        """Get complete billing summary for a member"""
        bills = BillMembership.objects.filter(membership=membership)
        
        summary = {
            'total_due': sum(b.amount_due for b in bills),
            'total_paid': sum(b.amount_paid_total for b in bills),
            'balance': sum(b.balance for b in bills),
            'bills': []
        }
        
        for bill_membership in bills:
            summary['bills'].append({
                'bill_id': bill_membership.bill.id,
                'bill_title': bill_membership.bill.title,
                'amount_due': bill_membership.amount_due,
                'amount_paid': bill_membership.amount_paid_total,
                'balance': bill_membership.balance,
                'status': bill_membership.status,
                'due_date': bill_membership.bill.due_date
            })
        
        return summary
```

---

## Phase 7: URL Configuration

```python
# campus_nexus/urls.py (or routing config)

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

# Association-level endpoints
router.register(
    r'associations/(?P<association_id>\d+)/billable-items',
    views.BillableItemViewSet,
    basename='billable-item'
)
router.register(
    r'associations/(?P<association_id>\d+)/bills',
    views.BillViewSet,
    basename='bill'
)

# Bill-specific nested endpoints
router.register(
    r'bills/(?P<bill_id>\d+)/memberships',
    views.BillMembershipViewSet,
    basename='bill-membership'
)

urlpatterns = [
    path('api/', include(router.urls)),
]
```

---

## Phase 8: Migration Strategy

### 8.1 Required Migrations

1. Create `BillableItem` model
2. Create `Bill` model
3. Create `BillMembership` model
4. Add `bill_membership` foreign key to `Charge` model
5. Create indexes on frequently queried fields

### 8.2 Data Migration (if needed)

Convert existing Charges to Bills if applicable:

```python
# campus_nexus/migrations/XXXX_create_billing_models.py

from django.db import migrations

def create_bills_from_charges(apps, schema_editor):
    """Convert legacy charges to new bill structure"""
    # Implementation depends on current data structure
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('campus_nexus', 'XXXX'),
    ]

    operations = [
        migrations.CreateModel(...),  # BillableItem
        migrations.CreateModel(...),  # Bill
        migrations.CreateModel(...),  # BillMembership
        migrations.AddField(...),     # Add bill_membership to Charge
        migrations.RunPython(create_bills_from_charges),
    ]
```

---

## Phase 9: Frontend Considerations

### 9.1 Admin Dashboard Views

1. **BillableItems Management**
   - Create, edit, delete templates
   - View usage statistics
   - Enable/disable templates

2. **Bills Management**
   - Create bills from templates
   - View draft/active/cancelled bills
   - Attach to members (selective or all)
   - View payment progress

3. **Member Billing View**
   - Select members to attach bill to
   - Filter by status, date range
   - Quick actions: waive, resend reminder

4. **Balance Tracking Dashboard**
   - Overall collection statistics
   - Per-member balance view
   - Payment timeline
   - Outstanding bills report

### 9.2 API Response Examples

**Create Bill Response:**
```json
{
  "id": 1,
  "association": 1,
  "billable_item": 1,
  "title": "Event Fee - Annual Gala 2026",
  "amount": "50000.00",
  "status": "draft",
  "attachment_type": "selective",
  "due_date": "2026-06-30",
  "issue_date": "2026-05-18",
  "total_members_billed": 0,
  "total_amount_due": "0.00",
  "total_amount_collected": "0.00"
}
```

**Member Balance Summary:**
```json
{
  "member_id": 5,
  "member_name": "John Doe",
  "total_due": "150000.00",
  "total_paid": "50000.00",
  "balance": "100000.00",
  "bills": [
    {
      "bill_id": 1,
      "bill_title": "Event Fee",
      "amount_due": "50000.00",
      "amount_paid": "50000.00",
      "balance": "0.00",
      "status": "paid",
      "due_date": "2026-06-30"
    },
    {
      "bill_id": 2,
      "bill_title": "Membership Renewal",
      "amount_due": "100000.00",
      "amount_paid": "0.00",
      "balance": "100000.00",
      "status": "unpaid",
      "due_date": "2026-07-15"
    }
  ]
}
```

---

## Phase 10: Testing Strategy

### 10.1 Unit Tests

- BillableItem creation & validation
- Bill creation from templates
- Member attachment (selective & all)
- Balance calculations
- Status transitions

### 10.2 Integration Tests

- Create bill → Attach members → Record payment → Verify balance
- Waive bill → Verify status update
- Permissions checks for different user roles

### 10.3 Edge Cases

- Negative amounts rejection
- Duplicate bill attachments
- Concurrent payment recording
- Waived bill cannot be re-attached
- Cancel bill cascading

---

## Implementation Checklist

- [ ] Phase 1: Create models & migrations
- [ ] Phase 2: Implement permission classes
- [ ] Phase 3: Build API endpoints
- [ ] Phase 4: Create serializers
- [ ] Phase 5: Implement views/viewsets
- [ ] Phase 6: Add signals & business logic
- [ ] Phase 7: Configure URLs
- [ ] Phase 8: Run migrations
- [ ] Phase 9: Frontend integration
- [ ] Phase 10: Write tests
- [ ] Code review & QA
- [ ] Deploy to staging
- [ ] User testing & feedback
- [ ] Deploy to production

---

## Future Enhancements

1. **Recurring Bills**: Auto-generate bills monthly/yearly
2. **Payment Reminders**: Send automated reminders before due date
3. **Bill Templates**: Save bill configurations for reuse
4. **Bulk Operations**: Apply bill to multiple associations
5. **Analytics**: Revenue reports, payment trends
6. **Integration**: SMS/Email notifications for payments
7. **Audit Trail**: Track all bill modifications
8. **Custom Payment Plans**: Installment-based billing
9. **Multi-currency Support**: Handle different currencies
10. **API Webhooks**: Notify external systems on state changes

---

## Notes

- All timestamps should use Django's `timezone.now()`
- All monetary amounts use Decimal fields (not float) for precision
- Superuser always has access; check association admin status for restricted users
- Consider soft-delete for Bills instead of hard delete (audit trail)
- Use `select_related()` and `prefetch_related()` for query optimization
