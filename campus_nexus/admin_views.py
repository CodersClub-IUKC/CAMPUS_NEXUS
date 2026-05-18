from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import admin as dj_admin, messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from .models import Bill, BillMembership, Membership, Association, BillableItem

def _admin_ctx(request):
    """Return the full Django admin context needed to render the sidebar/navigation."""
    return dj_admin.site.each_context(request)

@staff_member_required
@require_http_methods(["GET", "POST"])
def attach_bill_to_members(request, bill_id):
    """Custom view to attach bill to selective members"""
    
    bill = Bill.objects.get(id=bill_id)
    
    # Permission check
    if not request.user.is_superuser:
        try:
            assoc_admin = request.user.association_admin
            if assoc_admin.association_id != bill.association_id:
                return HttpResponseForbidden("Access denied")
        except:
            return HttpResponseForbidden("Access denied")
    
    if request.method == 'POST':
        member_ids = request.POST.getlist('members')
        members = Membership.objects.filter(
            id__in=member_ids,
            association_id=bill.association_id
        ).exclude(bills__bill=bill)
        
        # Use bulk_create
        bill_memberships = [
            BillMembership(
                bill=bill,
                membership=membership,
                amount_due=bill.amount
            ) for membership in members
        ]
        BillMembership.objects.bulk_create(bill_memberships, ignore_conflicts=True)
        created_count = len(bill_memberships)
        
        # Mark bill as active if draft
        if bill.status == 'draft':
            bill.status = 'active'
            bill.save(update_fields=['status'])
        
        messages.success(
            request,
            f"Added {created_count} new member(s)."
        )
        
        return redirect('admin:campus_nexus_bill_change', bill_id)
    
    # GET - Show member selection form
    existing_members = bill.memberships.values_list('membership_id', flat=True)
    available_members = Membership.objects.filter(
        association_id=bill.association_id,
        status='active'
    ).exclude(id__in=existing_members).select_related('member')
    
    context = {
        **_admin_ctx(request),
        'bill': bill,
        'available_members': available_members,
        'title': f'Attach "{bill.title}" to Members',
    }
    
    return render(request, 'admin/attach_members.html', context)

@staff_member_required
@require_http_methods(["GET", "POST"])
def waive_bill_membership(request, billmembership_id):
    """Custom view to waive a bill with reason"""
    
    bill_membership = BillMembership.objects.get(id=billmembership_id)
    
    # Permission check
    if not request.user.is_superuser:
        try:
            assoc_admin = request.user.association_admin
            if assoc_admin.association_id != bill_membership.bill.association_id:
                return HttpResponseForbidden("Access denied")
        except:
            return HttpResponseForbidden("Access denied")
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        
        # Implemented amount_waived logic
        paid = bill_membership.amount_paid_total
        waivable_amount = max(0, bill_membership.amount_due - paid)
        
        bill_membership.amount_waived = waivable_amount
        bill_membership.status = 'waived'
        bill_membership.waived_at = timezone.now()
        bill_membership.waived_by = request.user
        bill_membership.waive_reason = reason
        bill_membership.save()
        
        messages.success(request, f"Bill waived for {bill_membership.membership.member.full_name}")
        return redirect('admin:campus_nexus_billmembership_change', billmembership_id)
    
    context = {
        **_admin_ctx(request),
        'bill_membership': bill_membership,
        'title': f'Waive Bill: {bill_membership.membership.member.full_name}',
    }
    
    return render(request, 'admin/waive_bill.html', context)

@staff_member_required
@require_http_methods(["GET"])
def billing_dashboard(request, association_id=None):
    """Dashboard showing billing statistics"""
    
    # Permission check and association filtering
    if request.user.is_superuser and association_id:
        association = Association.objects.get(id=association_id)
    elif request.user.is_superuser:
        association = Association.objects.first() # Or prompt to select
    else:
        try:
            assoc_admin = request.user.association_admin
            association = assoc_admin.association
        except:
            return HttpResponseForbidden("Access denied")
            
    if not association:
         return render(request, 'admin/billing_dashboard.html', {
            **_admin_ctx(request),
            'title': 'Billing Dashboard',
            'no_association': True,
         })
    
    # Get statistics using annotations to fix N+1
    bills = Bill.objects.filter(association=association, status='active').annotate(
        members_count=Count('memberships', filter=~Q(memberships__status='cancelled'), distinct=True),
        total_due=Sum('memberships__amount_due', filter=~Q(memberships__status='cancelled')),
        total_collected=Sum('memberships__charges__payments__amount_paid', filter=Q(memberships__charges__payments__status='recorded')),
        total_waived=Sum('memberships__amount_waived', filter=~Q(memberships__status='cancelled'))
    )
    
    total_billed = sum(b.total_due or 0 for b in bills)
    total_collected = sum(b.total_collected or 0 for b in bills)
    total_waived = sum(b.total_waived or 0 for b in bills)
    total_outstanding = total_billed - total_collected - total_waived
    bills_count = len(bills)
    members_count = sum(b.members_count or 0 for b in bills)
    
    bill_stats = []
    
    for bill in bills:
        b_due = bill.total_due or 0
        b_collected = bill.total_collected or 0
        b_waived = bill.total_waived or 0
        b_balance = max(0, b_due - b_collected - b_waived)
        
        bill_stats.append({
            'bill': bill,
            'members': bill.members_count or 0,
            'due': b_due,
            'collected': b_collected,
            'balance': b_balance,
            'paid_percentage': (b_collected / b_due * 100) if b_due > 0 else 0
        })
    
    # Get members with outstanding balance
    outstanding_members = BillMembership.objects.filter(
        bill__association=association,
        bill__status='active'
    ).exclude(status__in=['paid', 'waived', 'cancelled']).select_related(
        'membership__member', 'bill'
    ).annotate(
        paid_total=Sum('charges__payments__amount_paid', filter=Q(charges__payments__status='recorded'))
    )
    
    outstanding_list = []
    for bm in outstanding_members[:20]:
        paid = bm.paid_total or 0
        balance = bm.amount_due - paid - bm.amount_waived
        if balance > 0:
            outstanding_list.append({
                'bm': bm,
                'balance': balance
            })
    
    context = {
        **_admin_ctx(request),
        'association': association,
        'total_billed': total_billed,
        'total_collected': total_collected,
        'total_outstanding': total_outstanding,
        'collection_rate': (total_collected / total_billed * 100) if total_billed > 0 else 0,
        'bills_count': bills_count,
        'members_count': members_count,
        'bill_stats': bill_stats,
        'outstanding_members': outstanding_list,
        'title': f'Billing Dashboard - {association.name}',
    }
    
    return render(request, 'admin/billing_dashboard.html', context)
