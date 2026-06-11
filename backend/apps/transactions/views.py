from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination
from core.permissions import require_org_param

from .ingestion import CsvImportSource, ManualEntrySource
from .models import Transaction
from .rollup import ROLLUP_DIMENSIONS, rollup_by, rollup_by_tag
from .serializers import (
    CsvImportSerializer,
    TransactionCreateSerializer,
    TransactionSerializer,
)


def _filtered_queryset(request: Request, org):
    """Apply the shared list filters to an org-scoped transaction queryset."""
    qs = Transaction.objects.filter(org=org).select_related('counterparty', 'category')

    source = request.query_params.get('source')
    if source:
        qs = qs.filter(source=source)

    counterparty = request.query_params.get('counterparty')
    if counterparty:
        qs = qs.filter(counterparty_id=counterparty)

    cp_type = request.query_params.get('counterparty_type')
    if cp_type:
        qs = qs.filter(counterparty__type=cp_type)

    category = request.query_params.get('category')
    if category:
        qs = qs.filter(category_id=category)

    direction = request.query_params.get('direction')
    if direction == 'inflow':
        qs = qs.filter(amount__gte=0)
    elif direction == 'outflow':
        qs = qs.filter(amount__lt=0)

    date_from = request.query_params.get('from')
    if date_from:
        qs = qs.filter(timestamp__date__gte=date_from)
    date_to = request.query_params.get('to')
    if date_to:
        qs = qs.filter(timestamp__date__lte=date_to)

    return qs


class TransactionListCreateView(APIView):
    """GET/POST /api/v1/transactions/?org={org_id}

    GET lists (paginated, filterable). POST creates a single manual
    transaction through the ManualEntrySource so it shares the dedup pipeline.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        org = require_org_param(request)
        qs = _filtered_queryset(request, org)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = TransactionSerializer(page, many=True).data
        return paginator.get_paginated_response(data)

    def post(self, request: Request) -> Response:
        org = require_org_param(request)
        serializer = TransactionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        source = ManualEntrySource(org, entries=[serializer.validated_data])
        result = source.sync()
        if result.errors:
            return Response(
                {'detail': result.errors[0], 'code': 'INGESTION_ERROR'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Return the newest transaction for this org (the one just created), if any.
        latest = Transaction.objects.filter(org=org).order_by('-created_at').first()
        body = {'result': result.as_dict()}
        if latest is not None:
            body['transaction'] = TransactionSerializer(latest).data
        return Response(body, status=status.HTTP_201_CREATED)


class TransactionDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/transactions/{pk}/?org={org_id}"""
    permission_classes = (IsAuthenticated,)

    def _get(self, request: Request, pk: str) -> Transaction:
        org = require_org_param(request)
        return Transaction.objects.select_related('counterparty', 'category').get(id=pk, org=org)

    def get(self, request: Request, pk: str) -> Response:
        try:
            txn = self._get(request, pk)
        except Transaction.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(TransactionSerializer(txn).data)

    def patch(self, request: Request, pk: str) -> Response:
        try:
            txn = self._get(request, pk)
        except Transaction.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = TransactionSerializer(txn, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # A manual category change is a human correction (§5.2) — record it.
        if 'category' in serializer.validated_data:
            serializer.validated_data['category_overridden'] = True
        serializer.save()
        return Response(serializer.data)

    def delete(self, request: Request, pk: str) -> Response:
        try:
            txn = self._get(request, pk)
        except Transaction.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        txn.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TransactionCsvImportView(APIView):
    """POST /api/v1/transactions/import-csv/?org={org_id}"""
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        org = require_org_param(request)
        serializer = CsvImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            source = CsvImportSource(
                org,
                content=serializer.validated_data['content'],
                preset=serializer.validated_data.get('preset'),
                column_map=serializer.validated_data.get('column_map'),
            )
            result = source.sync()
        except ValueError as exc:
            return Response(
                {'detail': str(exc), 'code': 'CSV_IMPORT_ERROR'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'result': result.as_dict()}, status=status.HTTP_201_CREATED)


class TransactionRollupView(APIView):
    """GET /api/v1/transactions/rollup/?org={org_id}&by={dimension}

    Categorised inflow/outflow/net rollup. ``by`` is one of
    counterparty_type, category, counterparty, source, or tag.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        org = require_org_param(request)
        dimension = request.query_params.get('by', 'counterparty_type')

        if dimension == 'tag':
            rows = rollup_by_tag(org)
        elif dimension in ROLLUP_DIMENSIONS:
            rows = rollup_by(org, dimension)
        else:
            valid = ', '.join(sorted([*ROLLUP_DIMENSIONS, 'tag']))
            return Response(
                {'detail': f'Invalid "by" dimension. Choose one of: {valid}.', 'code': 'INVALID_DIMENSION'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'dimension': dimension, 'groups': rows})
