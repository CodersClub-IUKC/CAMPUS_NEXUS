from campus_nexus.models import AuditLog


def _infer_association(obj):
    association = getattr(obj, "association", None)
    if association is not None:
        return association

    membership = getattr(obj, "membership", None)
    if membership is not None:
        return getattr(membership, "association", None)

    return None


def record_audit_event(*, actor, action: str, obj, association=None, metadata=None):
    association = association or _infer_association(obj)
    metadata = metadata or {}

    AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        association=association,
        action=action,
        model_name=obj._meta.label_lower,
        object_id=str(getattr(obj, "pk", "") or ""),
        object_repr=str(obj)[:255],
        metadata=metadata,
    )
