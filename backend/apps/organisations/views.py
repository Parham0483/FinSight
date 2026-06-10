from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Organisation, OrgMembership
from .serializers import OrganisationCreateSerializer, OrganisationSerializer


class OrgListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        org_ids = OrgMembership.objects.filter(user=request.user).values_list('org_id', flat=True)
        orgs = Organisation.objects.filter(id__in=org_ids).order_by('created_at')
        return Response(OrganisationSerializer(orgs, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = OrganisationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            org: Organisation = serializer.save()
            OrgMembership.objects.create(user=request.user, org=org, role='owner')
        return Response(OrganisationSerializer(org).data, status=status.HTTP_201_CREATED)


class OrgDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def _get_org(self, request: Request, pk: str) -> Organisation | None:
        try:
            membership = OrgMembership.objects.select_related('org').get(user=request.user, org_id=pk)
            return membership.org
        except OrgMembership.DoesNotExist:
            return None

    def get(self, request: Request, pk: str) -> Response:
        org = self._get_org(request, pk)
        if not org:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrganisationSerializer(org).data)

    def patch(self, request: Request, pk: str) -> Response:
        org = self._get_org(request, pk)
        if not org:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = OrganisationCreateSerializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OrganisationSerializer(org).data)
