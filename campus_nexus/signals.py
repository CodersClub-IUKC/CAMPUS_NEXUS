from django.dispatch import receiver
from django.db.models.signals import post_save

from .models import AssociationAdmin, Guild

@receiver(post_save, sender=AssociationAdmin)
def add_association_admin_model_permissions(sender, instance: AssociationAdmin, created: bool, **kwargs):
    """
    Ensure that when an AssociationAdmin is created, they are granted all necessary permissions
    for managing association-related models.
    """
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

@receiver(post_save, sender=Guild)
def add_guild_model_permissions(sender, instance: Guild, created: bool, **kwargs):
    """
    Ensure that when a Guild is created, its user is granted all necessary permissions
    for managing guild-related models.
    """
    print("="*100)
    print(f"Guild signal triggered for {instance.user.username}")
    if created:
        user = instance.user

        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from .models import Association, Member, Membership, Cabinet, CabinetMember, Fee, Payment, Event

        user.is_staff = True
        user.is_superuser = False
        user.save()

        # List of models related to the guild
        models = [Association, Member, Membership, Cabinet, CabinetMember, Fee, Payment, Event]

        for model in models:
            ct = ContentType.objects.get_for_model(model)
            perms = Permission.objects.filter(content_type=ct)
            user.user_permissions.add(*perms)
        