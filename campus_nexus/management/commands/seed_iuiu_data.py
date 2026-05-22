from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from campus_nexus.models import (
    Faculty, Course, Association, AssociationAdmin,
    Member, Membership, Fee, BillableItem, Bill, BillMembership, Payment, Charge
)
from decimal import Decimal
from django.utils import timezone
import datetime

class Command(BaseCommand):
    help = 'Seeds the database with Islamic University in Uganda (IUIU) data and selectable billing data.'

    def handle(self, *args, **kwargs):
        from django.conf import settings
        original_email_backend = settings.EMAIL_BACKEND
        settings.EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
        try:
            self.stdout.write("Starting IUIU database seed...")

            # 1. Create User
            admin_user, created = User.objects.get_or_create(username='iuiu_admin', defaults={
                'email': 'iuiu_admin@iuiu.ac.ug',
                'is_staff': True,
            })
            if created:
                admin_user.set_password('password123')
                admin_user.save()
                self.stdout.write(self.style.SUCCESS('Created admin user: iuiu_admin (password: password123)'))

            # 2. Faculties & Courses
            fac_science, _ = Faculty.objects.get_or_create(name='Faculty of Science')
            fac_law, _ = Faculty.objects.get_or_create(name='Faculty of Law')
            fac_manage, _ = Faculty.objects.get_or_create(name='Faculty of Management Studies')
            
            cs_course, _ = Course.objects.get_or_create(name='BSc Computer Science', faculty=fac_science, duration_years=3)
            law_course, _ = Course.objects.get_or_create(name='Bachelor of Laws (LLB)', faculty=fac_law, duration_years=4)

            # 3. Associations
            iusa, _ = Association.objects.get_or_create(name='IUIU Computing Students Association (IUSA)', defaults={
                'faculty': fac_science,
                'description': 'The umbrella association for all computing and IT students at IUIU.'
            })
            law_soc, _ = Association.objects.get_or_create(name='IUIU Law Society', defaults={
                'faculty': fac_law,
                'description': 'The representative body of all law students.'
            })
            
            # 4. Association Admin
            assoc_admin, created = AssociationAdmin.objects.get_or_create(user=admin_user, defaults={
                'association': iusa,
                'title': 'IUSA President'
            })
            
            # 5. Members and Memberships
            members_data = [
                {'first': 'Ahmed', 'last': 'Ali', 'reg': '111/CS/2026', 'email': 'ahmed@iuiu.ac.ug', 'course': cs_course},
                {'first': 'Fatuma', 'last': 'Namaganda', 'reg': '112/CS/2026', 'email': 'fatuma@iuiu.ac.ug', 'course': cs_course},
                {'first': 'Umar', 'last': 'Kato', 'reg': '113/CS/2026', 'email': 'umar@iuiu.ac.ug', 'course': cs_course},
                {'first': 'Aisha', 'last': 'Nakalema', 'reg': '211/LAW/2026', 'email': 'aisha@iuiu.ac.ug', 'course': law_course},
            ]
            
            created_memberships = []
            for d in members_data:
                member, _ = Member.objects.get_or_create(
                    registration_number=d['reg'],
                    defaults={
                        'first_name': d['first'],
                        'last_name': d['last'],
                        'email': d['email'],
                        'phone': '0700000000',
                        'member_type': 'student',
                        'course': d['course'],
                        'nationality': 'UG'
                    }
                )
                assoc = iusa if d['course'] == cs_course else law_soc
                membership, _ = Membership.objects.get_or_create(member=member, association=assoc)
                if assoc == iusa:
                    created_memberships.append(membership)
                    
            self.stdout.write(self.style.SUCCESS(f"Created {len(members_data)} members/memberships."))

            # 6. Selectable Billing setup for IUSA
            # Create Billable Items
            dinner_item, _ = BillableItem.objects.get_or_create(
                association=iusa, 
                name='IUSA End of Year Dinner 2026',
                defaults={
                    'description': 'Ticket for the grand end of year dinner.',
                    'amount': Decimal('50000.00'),
                    'category': 'event'
                }
            )
            hoodie_item, _ = BillableItem.objects.get_or_create(
                association=iusa, 
                name='IUSA Branded Hoodie',
                defaults={
                    'description': 'Official heavy cotton hoodie.',
                    'amount': Decimal('35000.00'),
                    'category': 'merchandise'
                }
            )
            
            # Create Bills (Active)
            dinner_bill, _ = Bill.objects.get_or_create(
                association=iusa,
                title='IUSA Dinner Ticket 2026',
                defaults={
                    'billable_item': dinner_item,
                    'description': 'Optional ticket purchase for the dinner.',
                    'amount': dinner_item.amount,
                    'issue_date': timezone.now().date(),
                    'due_date': timezone.now().date() + datetime.timedelta(days=30),
                    'attachment_type': 'selective',
                    'status': 'active'
                }
            )
            
            hoodie_bill, _ = Bill.objects.get_or_create(
                association=iusa,
                title='IUSA Hoodie Purchase',
                defaults={
                    'billable_item': hoodie_item,
                    'description': 'Pre-order your hoodie now.',
                    'amount': hoodie_item.amount,
                    'issue_date': timezone.now().date(),
                    'due_date': timezone.now().date() + datetime.timedelta(days=15),
                    'attachment_type': 'all',
                    'status': 'active'
                }
            )
            
            # Attach bills to members
            # All members get hoodie bill
            for m in created_memberships:
                bm, created = BillMembership.objects.get_or_create(
                    bill=hoodie_bill,
                    membership=m,
                    defaults={'amount_due': hoodie_bill.amount}
                )
                
            # Only Ahmed gets dinner bill
            if created_memberships:
                dinner_bm, _ = BillMembership.objects.get_or_create(
                    bill=dinner_bill,
                    membership=created_memberships[0],
                    defaults={'amount_due': dinner_bill.amount}
                )
                
                # Let's see if charge exists:
                charge = dinner_bm.charges.first()
                if not charge:
                    charge = Charge.objects.create(
                        association=iusa,
                        membership=created_memberships[0],
                        bill_membership=dinner_bm,
                        amount_due=dinner_bill.amount,
                        title=dinner_bill.title,
                        purpose='event',
                        status='unpaid',
                        due_date=dinner_bill.due_date,
                    )
                
                # Make payment
                Payment.objects.get_or_create(
                    membership=created_memberships[0],
                    charge=charge,
                    defaults={
                        'amount_paid': Decimal('20000.00'), # Partial
                        'payment_method': 'cash',
                        'status': 'recorded',
                        'recorded_by': admin_user
                    }
                )
                
                # Waive remaining 30k
                dinner_bm.amount_waived = Decimal('30000.00')
                dinner_bm.status = 'waived'
                dinner_bm.save()
                dinner_bm.update_status_from_payments() # Will update the charge

            self.stdout.write(self.style.SUCCESS("Successfully seeded IUIU data and selectable billing data!"))
        finally:
            settings.EMAIL_BACKEND = original_email_backend
