import logging

import magic
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organisations.models import Organisation, OrgMembership
from .models import Document, DocumentStorageSettings
from .serializers import (
    DocumentConfirmSerializer,
    DocumentSerializer,
    DocumentUploadSerializer,
    StorageSettingsSerializer,
    StorageSettingsUpdateSerializer,
)
from .services.storage import save_upload
from .tasks import process_document

logger = logging.getLogger(__name__)


def _get_org_or_403(request: Request, org_id: str) -> Organisation | Response:
    """Return org if user is a member, else a 403 Response."""
    try:
        org = Organisation.objects.get(id=org_id)
    except Organisation.DoesNotExist:
        return Response({'detail': 'Organisation not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not OrgMembership.objects.filter(user=request.user, org=org).exists():
        return Response({'detail': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

    return org


class DocumentListUploadView(APIView):
    """
    GET  /orgs/{org_id}/documents/          — list all documents
    POST /orgs/{org_id}/documents/          — upload new document
    """
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request: Request, org_id: str) -> Response:
        org = _get_org_or_403(request, org_id)
        if isinstance(org, Response):
            return org

        status_filter = request.query_params.get('status')
        type_filter = request.query_params.get('document_type')

        qs = Document.objects.filter(org=org).order_by('-uploaded_at')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if type_filter:
            qs = qs.filter(document_type=type_filter)

        serializer = DocumentSerializer(qs[:100], many=True)
        return Response(serializer.data)

    def post(self, request: Request, org_id: str) -> Response:
        org = _get_org_or_403(request, org_id)
        if isinstance(org, Response):
            return org

        upload_serializer = DocumentUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)

        uploaded_file = upload_serializer.validated_data['file']
        doc_type = upload_serializer.validated_data['document_type']

        file_bytes = uploaded_file.read()

        # Detect actual MIME type from file content (not just extension)
        detected_mime = magic.from_buffer(file_bytes, mime=True)

        # Get org storage settings (defaults to local if not configured)
        storage_cfg = DocumentStorageSettings.objects.filter(org=org).first()

        file_path = save_upload(
            org_id=str(org.id),
            file_bytes=file_bytes,
            filename=uploaded_file.name,
            mime_type=detected_mime,
            storage_settings=storage_cfg,
        )

        doc = Document.objects.create(
            org=org,
            uploaded_by=request.user,
            file_path=file_path,
            original_filename=uploaded_file.name,
            file_size_bytes=len(file_bytes),
            mime_type=detected_mime,
            document_type=doc_type,
            status='pending',
        )

        # Queue async processing
        process_document.delay(str(doc.id))

        return Response(DocumentSerializer(doc).data, status=status.HTTP_202_ACCEPTED)


class DocumentDetailView(APIView):
    """
    GET    /orgs/{org_id}/documents/{doc_id}/              — get document + extracted data
    DELETE /orgs/{org_id}/documents/{doc_id}/              — delete document
    """

    def _get_doc(self, request: Request, org_id: str, doc_id: str):
        org = _get_org_or_403(request, org_id)
        if isinstance(org, Response):
            return org, None
        try:
            doc = Document.objects.prefetch_related('line_items').get(id=doc_id, org=org)
            return org, doc
        except Document.DoesNotExist:
            return org, None

    def get(self, request: Request, org_id: str, doc_id: str) -> Response:
        org, doc = self._get_doc(request, org_id, doc_id)
        if isinstance(org, Response):
            return org
        if doc is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(DocumentSerializer(doc).data)

    def delete(self, request: Request, org_id: str, doc_id: str) -> Response:
        org, doc = self._get_doc(request, org_id, doc_id)
        if isinstance(org, Response):
            return org
        if doc is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentConfirmView(APIView):
    """
    POST /orgs/{org_id}/documents/{doc_id}/confirm/
    User reviews extracted data, confirms (with optional corrections),
    and optionally creates Invoice/Transaction/Customer records.
    """

    def post(self, request: Request, org_id: str, doc_id: str) -> Response:
        org = _get_org_or_403(request, org_id)
        if isinstance(org, Response):
            return org

        try:
            doc = Document.objects.get(id=doc_id, org=org, status='review')
        except Document.DoesNotExist:
            return Response(
                {'detail': 'Document not found or not in review status.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DocumentConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        confirmed_data = data['confirmed_data']
        created_invoice_id = None
        created_transaction_id = None
        created_customer_id = None

        # Optionally create records from confirmed data
        if data['create_customer']:
            created_customer_id = _create_customer(org, confirmed_data, doc.document_type)

        if data['create_invoice'] and doc.document_type in ('invoice', 'purchase_order'):
            created_invoice_id = _create_invoice(
                org, confirmed_data, doc.document_type, created_customer_id
            )

        Document.objects.filter(id=doc_id).update(
            status='confirmed',
            confirmed_data=confirmed_data,
            review_notes=data['review_notes'],
            confirmed_at=timezone.now(),
            created_invoice_id=created_invoice_id,
            created_transaction_id=created_transaction_id,
            created_customer_id=created_customer_id,
        )

        doc.refresh_from_db()
        return Response(DocumentSerializer(doc).data)


class DocumentRejectView(APIView):
    """POST /orgs/{org_id}/documents/{doc_id}/reject/ — reject extracted data."""

    def post(self, request: Request, org_id: str, doc_id: str) -> Response:
        org = _get_org_or_403(request, org_id)
        if isinstance(org, Response):
            return org

        try:
            doc = Document.objects.get(id=doc_id, org=org, status='review')
        except Document.DoesNotExist:
            return Response({'detail': 'Document not found or not in review status.'}, status=404)

        notes = request.data.get('review_notes', '')
        Document.objects.filter(id=doc_id).update(status='rejected', review_notes=notes)
        return Response({'detail': 'Document rejected.'})


class DocumentReprocessView(APIView):
    """POST /orgs/{org_id}/documents/{doc_id}/reprocess/ — re-run extraction."""

    def post(self, request: Request, org_id: str, doc_id: str) -> Response:
        org = _get_org_or_403(request, org_id)
        if isinstance(org, Response):
            return org

        try:
            doc = Document.objects.get(id=doc_id, org=org)
        except Document.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        if doc.status in ('pending', 'preprocessing', 'extracting'):
            return Response({'detail': 'Already processing.'}, status=status.HTTP_409_CONFLICT)

        Document.objects.filter(id=doc_id).update(
            status='pending',
            extracted_data=None,
            processing_error='',
            processing_tier_used=None,
            tokens_used=0,
            confidence_score=None,
        )
        process_document.delay(str(doc.id))
        return Response({'detail': 'Reprocessing queued.'})


class StorageSettingsView(APIView):
    """
    GET   /orgs/{org_id}/documents/storage/   — get current storage config
    PATCH /orgs/{org_id}/documents/storage/   — update storage config
    """

    BACKEND_OPTIONS = [
        {
            'value': 'local',
            'label': 'Local filesystem',
            'description': DocumentStorageSettings.BACKEND_DESCRIPTIONS['local'],
            'pros': ['Free', 'Simple', 'Works immediately', 'No external account needed'],
            'cons': ['Lost if server disk fails without backup', 'Not suitable for multiple servers'],
            'recommended_for': 'Getting started, testing, low document volume',
        },
        {
            'value': 's3',
            'label': 'S3-compatible cloud storage',
            'description': DocumentStorageSettings.BACKEND_DESCRIPTIONS['s3'],
            'pros': ['99.999999999% durability', 'Scales to millions of files', 'CDN-ready', 'Cloudflare R2 has free tier'],
            'cons': ['Requires external account + credentials', 'Small ongoing cost at volume'],
            'recommended_for': 'Any business handling financial documents seriously',
        },
        {
            'value': 'supabase',
            'label': 'Supabase Storage',
            'description': DocumentStorageSettings.BACKEND_DESCRIPTIONS['supabase'],
            'pros': ['Integrated with Supabase DB', 'Row-level security', 'Free tier generous'],
            'cons': ['Supabase account required'],
            'recommended_for': 'Teams already using Supabase',
        },
    ]

    def get(self, request: Request, org_id: str) -> Response:
        org = _get_org_or_403(request, org_id)
        if isinstance(org, Response):
            return org

        cfg = DocumentStorageSettings.objects.filter(org=org).first()
        return Response({
            'current': StorageSettingsSerializer(cfg).data if cfg else None,
            'options': self.BACKEND_OPTIONS,
        })

    def patch(self, request: Request, org_id: str) -> Response:
        org = _get_org_or_403(request, org_id)
        if isinstance(org, Response):
            return org

        cfg, _ = DocumentStorageSettings.objects.get_or_create(org=org)
        serializer = StorageSettingsUpdateSerializer(cfg, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(StorageSettingsSerializer(updated).data)


# ── Helper functions for record creation ─────────────────────────────────


def _create_customer(org, confirmed_data: dict, doc_type: str) -> str | None:
    """Create a Customer record from extracted vendor/payee name."""
    from apps.customers.models import Customer

    name = (
        confirmed_data.get('vendor_name')
        or confirmed_data.get('payee_name')
        or confirmed_data.get('supplier_name')
        or confirmed_data.get('merchant_name')
        or ''
    ).strip()

    if not name:
        return None

    customer, _ = Customer.objects.get_or_create(
        org=org,
        name=name,
        defaults={
            'email': confirmed_data.get('vendor_email', ''),
            'payment_terms_days': 30,
        },
    )
    return str(customer.id)


def _create_invoice(org, confirmed_data: dict, doc_type: str, customer_id: str | None) -> str | None:
    """Create an Invoice record from confirmed invoice/PO data."""
    from datetime import date
    from apps.customers.models import Invoice, Customer

    total = confirmed_data.get('total_amount')
    if not total:
        return None

    due_date_str = confirmed_data.get('due_date') or confirmed_data.get('expected_delivery_date') or ''
    issue_date_str = confirmed_data.get('issue_date') or ''

    def _parse_date(s: str) -> date:
        try:
            return date.fromisoformat(s[:10])
        except (ValueError, TypeError):
            return date.today()

    customer = Customer.objects.filter(id=customer_id, org=org).first() if customer_id else None

    invoice = Invoice.objects.create(
        org=org,
        customer=customer,
        reference=confirmed_data.get('invoice_number') or confirmed_data.get('po_number') or '',
        amount=total,
        currency=confirmed_data.get('currency', 'GBP'),
        issue_date=_parse_date(issue_date_str),
        due_date=_parse_date(due_date_str),
        status='unpaid',
        notes=confirmed_data.get('notes', ''),
    )
    return str(invoice.id)
