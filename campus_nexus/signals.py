from django.dispatch import receiver
from django.db.models.signals import post_save

from .models import AssociationAdmin

@receiver(post_save, sender=AssociationAdmin)
def add_model_permissions(sender, instance: AssociationAdmin, created: bool, **kwargs):
    """
    Ensure that when an AssociationAdmin is created, they are granted all necessary permissions
    for managing association-related models.
    """
    print("="*100)
    print("Signal triggered for AssociationAdmin creation.")
    if created:
        user = instance.user
        association = instance.association

        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from .models import Association, Member, Membership, Cabinet, CabinetMember, Fee, Payment, Event

        user.is_staff = True
        user.is_superuser = False
        user.save()

        # List of models related to the association
        models = [Association, Member, Membership, Cabinet, CabinetMember, Fee, Payment, Event]

        for model in models:
            ct = ContentType.objects.get_for_model(model)
            perms = Permission.objects.filter(content_type=ct)
            user.user_permissions.add(*perms)
        