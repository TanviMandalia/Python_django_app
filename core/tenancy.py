from django.core.exceptions import PermissionDenied


def resolve_hospital(user):
    """Resolve a non-platform user's clinic from server-side profile relations."""
    if not user or not user.is_authenticated or user.is_superuser:
        return None

    for relation in ("clinic_admin_profile", "staff_profile"):
        profile = getattr(user, relation, None)
        if profile is not None and profile.hospital_id:
            return profile.hospital

    appointment = (
        user.appointments.filter(hospital__isnull=False)
        .select_related("hospital")
        .order_by("-created_at")
        .first()
    )
    return appointment.hospital if appointment else None


def require_hospital(user):
    hospital = resolve_hospital(user)
    if hospital is None:
        raise PermissionDenied("No clinic is associated with this account.")
    return hospital