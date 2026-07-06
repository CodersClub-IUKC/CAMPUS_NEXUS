from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import admin as dj_admin, messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from .models import Bill, BillMembership, Membership, Association, BillableItem
from .services.import_export.centre import (
    ImportExportError,
    build_preview,
    commit_preview,
    export_csv_response,
    export_excel_response,
    get_spec,
    modules_for_request,
    preview_from_session,
    preview_to_session,
)

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


@staff_member_required
@require_http_methods(["GET"])
def import_export_centre(request):
    context = {
        **_admin_ctx(request),
        "title": "Import & Export Centre",
        "sections": modules_for_request(request),
    }
    return render(request, "admin/import_export/centre.html", context)


@staff_member_required
@require_http_methods(["GET", "POST"])
def import_export_upload(request, module_key):
    try:
        spec = get_spec(module_key)
    except ImportExportError:
        return HttpResponseForbidden("Unsupported module")

    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        mode = request.POST.get("mode") or "create"
        if not uploaded_file:
            messages.error(request, "Choose a CSV or Excel file to import.")
        else:
            try:
                preview = build_preview(request, module_key, uploaded_file, mode)
            except PermissionDenied:
                return HttpResponseForbidden("Access denied")
            except ImportExportError as exc:
                messages.error(request, str(exc))
            except Exception as exc:
                messages.error(request, f"Import validation failed: {exc}")
            else:
                request.session[f"import_preview:{module_key}"] = preview_to_session(preview)
                return redirect("admin:import_export_preview", module_key=module_key)

    context = {
        **_admin_ctx(request),
        "title": f"Import {spec.label}",
        "spec": spec,
    }
    return render(request, "admin/import_export/upload.html", context)


@staff_member_required
@require_http_methods(["GET", "POST"])
def import_export_preview(request, module_key):
    session_key = f"import_preview:{module_key}"
    value = request.session.get(session_key)
    if not value:
        messages.warning(request, "No pending import preview was found.")
        return redirect("admin:import_export_centre")

    preview = preview_from_session(value)
    if request.method == "POST":
        if "cancel" in request.POST:
            request.session.pop(session_key, None)
            messages.info(request, "Import cancelled.")
            return redirect("admin:import_export_centre")
        try:
            summary = commit_preview(request, preview)
        except PermissionDenied:
            return HttpResponseForbidden("Access denied")
        except Exception as exc:
            messages.error(request, f"Import failed and was rolled back: {exc}")
        else:
            request.session.pop(session_key, None)
            messages.success(
                request,
                "Import complete. "
                f"Created: {summary['created']}. Updated: {summary['updated']}. Skipped: {summary['skipped']}.",
            )
            return redirect("admin:import_export_centre")

    context = {
        **_admin_ctx(request),
        "title": f"Preview {preview['module_label']} Import",
        "preview": preview,
    }
    return render(request, "admin/import_export/preview.html", context)


@staff_member_required
@require_http_methods(["GET"])
def import_export_export(request, module_key, file_type):
    try:
        if file_type == "csv":
            return export_csv_response(request, module_key)
        if file_type == "xlsx":
            return export_excel_response(request, module_key)
    except PermissionDenied:
        return HttpResponseForbidden("Access denied")
    except ImportExportError as exc:
        messages.error(request, str(exc))
        return redirect("admin:import_export_centre")
    return HttpResponseForbidden("Unsupported export type")


@staff_member_required
@require_http_methods(["GET"])
def import_export_template(request, module_key, file_type):
    try:
        if file_type == "csv":
            return export_csv_response(request, module_key, template=True)
        if file_type == "xlsx":
            return export_excel_response(request, module_key, template=True)
    except PermissionDenied:
        return HttpResponseForbidden("Access denied")
    except ImportExportError as exc:
        messages.error(request, str(exc))
        return redirect("admin:import_export_centre")
    return HttpResponseForbidden("Unsupported template type")
