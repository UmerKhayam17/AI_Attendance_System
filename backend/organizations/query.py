def parse_branch_id(request):
    raw = request.query_params.get("branch") if hasattr(request, "query_params") else None
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def branch_of_org(organization, branch_id):
    from organizations.models import Branch

    if not branch_id or organization is None:
        return None
    return Branch.objects.filter(organization=organization, pk=branch_id).first()
