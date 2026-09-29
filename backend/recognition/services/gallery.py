from employees.models import Employee
from recognition.models import FaceEnrollment


def vectors_for_enrollment(enrollment: FaceEnrollment) -> list[list[float]]:
    raw = enrollment.embeddings
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, (int, float)):
            return [raw]
        return [v for v in raw if isinstance(v, list) and v]
    if enrollment.embedding:
        return [enrollment.embedding]
    return []


def build_gallery(organization=None, organization_id: int | None = None) -> dict[str, list[list[float]]]:
    gallery: dict[str, list[list[float]]] = {}
    qs = FaceEnrollment.objects.filter(
        is_trained=True,
        employee__is_active=True,
    ).select_related("employee")
    if organization is not None:
        qs = qs.filter(employee__organization=organization)
    elif organization_id is not None:
        qs = qs.filter(employee__organization_id=organization_id)
    else:
        return {}

    for enrollment in qs:
        vectors = vectors_for_enrollment(enrollment)
        if not vectors:
            continue
        gallery[enrollment.employee.employee_id] = vectors
    return gallery


def employee_in_gallery(organization, employee_id: str) -> Employee | None:
    return Employee.objects.filter(
        employee_id=employee_id,
        is_active=True,
        organization=organization,
        face_enrollment__is_trained=True,
    ).first()
