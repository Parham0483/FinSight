"""Shared org-membership access helpers.

Every domain resource in FinSight is org-scoped. These helpers centralise the
"is this user a member of this org?" check so views don't re-implement it.
"""
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request

from apps.organisations.models import Organisation, OrgMembership


def get_member_org(request: Request, org_id: str) -> Organisation:
    """Return the org if the requesting user is a member, else raise.

    Raises ``NotFound`` if the org does not exist and ``PermissionDenied`` if
    the user is not a member — mirroring the pattern used across the API.
    """
    try:
        org = Organisation.objects.get(id=org_id)
    except (Organisation.DoesNotExist, ValueError, TypeError):
        raise NotFound('Organisation not found.')

    if not OrgMembership.objects.filter(user=request.user, org=org).exists():
        raise PermissionDenied('You do not have access to this organisation.')

    return org


def require_org_param(request: Request) -> Organisation:
    """Resolve and authorise the org from the ``org`` query/body parameter."""
    org_id = request.query_params.get('org') or request.data.get('org')
    if not org_id:
        raise NotFound('Missing required "org" parameter.')
    return get_member_org(request, org_id)
