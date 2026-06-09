import logging
from datetime import datetime

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def process_document(self, document_id: str) -> dict:
    """
    Async document processing pipeline.
    Runs after upload — takes a Document from 'pending' to 'review'.

    Steps:
    1. Load file bytes from storage
    2. Run 4-tier extraction engine
    3. Run fuzzy matching against existing records
    4. Save results, set status to 'review'
    """
    from .models import Document, DocumentLineItem
    from .services.extraction import extract_document
    from .services.matching import find_matches
    from .services.storage import load_file

    try:
        doc = Document.objects.select_related('org').get(id=document_id)
        doc.status = 'preprocessing'
        doc.save(update_fields=['status'])

        # Load storage settings for this org
        storage_cfg = getattr(doc.org, 'storage_settings', None)

        # Load raw file bytes
        file_bytes = load_file(doc.file_path, storage_cfg)

        # Run extraction
        doc.status = 'extracting'
        doc.save(update_fields=['status'])

        extraction = extract_document(
            file_bytes=file_bytes,
            mime_type=doc.mime_type or 'application/pdf',
            document_type=doc.document_type,
        )

        # Run matching
        match = find_matches(
            org_id=str(doc.org_id),
            extracted_data=extraction.data,
            document_type=doc.document_type,
        )

        # Merge match suggestions into extracted data
        extracted_with_matches = {
            **extraction.data,
            '_match': {
                'customer_id': match.customer_id,
                'customer_name': match.customer_name,
                'customer_match_score': match.customer_match_score,
                'is_likely_duplicate': match.is_likely_duplicate,
                'duplicate_document_id': match.duplicate_document_id,
                'suggested_category': match.suggested_category,
                'warnings': match.warnings,
            },
        }

        # Save line items if present
        line_items_data = extraction.data.get('line_items', [])
        if line_items_data:
            DocumentLineItem.objects.filter(document=doc).delete()
            line_item_objs = [
                DocumentLineItem(
                    document=doc,
                    description=item.get('description', ''),
                    quantity=item.get('quantity'),
                    unit_price=item.get('unit_price'),
                    total=item.get('total'),
                    currency=item.get('currency', 'GBP'),
                    tax_amount=item.get('tax_amount'),
                    sort_order=idx,
                )
                for idx, item in enumerate(line_items_data)
            ]
            DocumentLineItem.objects.bulk_create(line_item_objs)

        # Update document
        Document.objects.filter(id=document_id).update(
            status='review',
            processing_tier_used=extraction.tier_used,
            tokens_used=extraction.tokens_used,
            confidence_score=extraction.confidence_score,
            extracted_data=extracted_with_matches,
            processed_at=datetime.utcnow(),
            processing_error='',
        )

        logger.info(
            'Document %s processed: tier=%d confidence=%.2f tokens=%d',
            document_id, extraction.tier_used, extraction.confidence_score, extraction.tokens_used,
        )

        return {
            'document_id': document_id,
            'tier_used': extraction.tier_used,
            'confidence': extraction.confidence_score,
            'tokens': extraction.tokens_used,
        }

    except Exception as exc:
        logger.exception('Document processing failed for %s: %s', document_id, exc)
        Document.objects.filter(id=document_id).update(
            status='failed',
            processing_error=str(exc),
        )
        raise self.retry(exc=exc)
