from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import require_org_param

from .models import Counterparty
from .serializers import CounterpartySerializer, MergeSerializer
from .services import merge_counterparties


class CounterpartyListCreateView(APIView):
    """GET/POST /api/v1/counterparties/?org={org_id}

    GET supports filtering by ``type``, ``tag``, and a free-text ``search`` over
    the name. Merged entries are hidden by default (``?include_merged=true`` to
    show them).
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        org = require_org_param(request)
        qs = Counterparty.objects.filter(org=org)

        if request.query_params.get('include_merged') != 'true':
            qs = qs.filter(merged_into__isnull=True)

        cp_type = request.query_params.get('type')
        if cp_type:
            qs = qs.filter(type=cp_type)

        tag = request.query_params.get('tag')
        if tag:
            qs = qs.filter(tags__contains=[tag])

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search)

        return Response(CounterpartySerializer(qs, many=True).data)

    def post(self, request: Request) -> Response:
        org = require_org_param(request)
        serializer = CounterpartySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(org=org, is_auto_created=False)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CounterpartyDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/counterparties/{pk}/?org={org_id}"""
    permission_classes = (IsAuthenticated,)

    def _get(self, request: Request, pk: str) -> Counterparty:
        org = require_org_param(request)
        return Counterparty.objects.get(id=pk, org=org)

    def get(self, request: Request, pk: str) -> Response:
        try:
            cp = self._get(request, pk)
        except Counterparty.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(CounterpartySerializer(cp).data)

    def patch(self, request: Request, pk: str) -> Response:
        try:
            cp = self._get(request, pk)
        except Counterparty.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CounterpartySerializer(cp, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request: Request, pk: str) -> Response:
        try:
            cp = self._get(request, pk)
        except Counterparty.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        cp.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CounterpartyMergeView(APIView):
    """POST /api/v1/counterparties/{pk}/merge/?org={org_id}

    Soft-merges the path counterparty (source) into ``target`` from the body.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request, pk: str) -> Response:
        org = require_org_param(request)
        payload = MergeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            source = Counterparty.objects.get(id=pk, org=org)
            target = Counterparty.objects.get(id=payload.validated_data['target'], org=org)
        except Counterparty.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if source.id == target.id:
            return Response(
                {'detail': 'A counterparty cannot be merged into itself.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        survivor = merge_counterparties(source, target)
        return Response(CounterpartySerializer(survivor).data)
