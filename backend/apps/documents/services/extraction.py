"""
4-tier document extraction engine.

Tier 1: pdfplumber text extraction (free, 0 tokens)
Tier 2: Claude Haiku 4.5 with text (~$0.001)
Tier 3: Claude Haiku 4.5 vision on preprocessed image (~$0.003)
Tier 4: Claude Sonnet fallback for handwritten / complex docs (~$0.015)

Escalation triggers:
  Tier 1 → 2: clean text extracted from PDF
  Tier 1 → 3: PDF is scanned/image-only (no usable text)
  Tier 2 → 3: confidence < 0.85
  Tier 3 → 4: confidence < 0.75
"""

import base64
import io
import json
import logging
from dataclasses import dataclass
from typing import Optional

import pdfplumber
from anthropic import Anthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

HAIKU_MODEL = 'claude-haiku-4-5-20251001'
SONNET_MODEL = 'claude-sonnet-4-6'

TIER2_CONFIDENCE_THRESHOLD = 0.85
TIER3_CONFIDENCE_THRESHOLD = 0.75

# ── Pydantic schemas for structured extraction ─────────────────────────────


class LineItem(BaseModel):
    description: str = ''
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None
    currency: str = 'GBP'
    tax_amount: Optional[float] = None


class InvoiceExtraction(BaseModel):
    vendor_name: str = ''
    vendor_address: str = ''
    vendor_email: str = ''
    invoice_number: str = ''
    issue_date: str = ''           # ISO date string YYYY-MM-DD or empty
    due_date: str = ''
    payment_terms: str = ''        # e.g. 'NET30'
    subtotal: Optional[float] = None
    tax_total: Optional[float] = None
    total_amount: Optional[float] = None
    currency: str = 'GBP'
    line_items: list[LineItem] = Field(default_factory=list)
    notes: str = ''
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence_notes: str = ''     # explain what was unclear


class BankStatementExtraction(BaseModel):
    bank_name: str = ''
    account_holder: str = ''
    account_number: str = ''
    sort_code: str = ''
    iban: str = ''
    currency: str = 'GBP'
    statement_from: str = ''
    statement_to: str = ''
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    transactions: list[dict] = Field(default_factory=list)  # [{date, description, amount, balance}]
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence_notes: str = ''


class ReceiptExtraction(BaseModel):
    merchant_name: str = ''
    merchant_address: str = ''
    date: str = ''
    time: str = ''
    items: list[LineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total_amount: Optional[float] = None
    currency: str = 'GBP'
    payment_method: str = ''       # cash, card, bank transfer
    category_hint: str = ''        # suggested transaction category
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence_notes: str = ''


class ChequeExtraction(BaseModel):
    payee_name: str = ''
    amount: Optional[float] = None
    amount_words: str = ''         # written amount on cheque
    currency: str = 'GBP'
    date: str = ''
    cheque_number: str = ''
    bank_name: str = ''
    account_holder: str = ''
    sort_code: str = ''
    account_number: str = ''
    memo: str = ''
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence_notes: str = ''


class PurchaseOrderExtraction(BaseModel):
    buyer_name: str = ''
    supplier_name: str = ''
    supplier_address: str = ''
    po_number: str = ''
    issue_date: str = ''
    expected_delivery_date: str = ''
    delivery_address: str = ''
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax_total: Optional[float] = None
    total_amount: Optional[float] = None
    currency: str = 'GBP'
    payment_terms: str = ''
    notes: str = ''
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence_notes: str = ''


SCHEMA_MAP = {
    'invoice': InvoiceExtraction,
    'bank_statement': BankStatementExtraction,
    'receipt': ReceiptExtraction,
    'cheque': ChequeExtraction,
    'purchase_order': PurchaseOrderExtraction,
}

# ── System prompt ──────────────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """
You are a financial document data extraction specialist for FinSight, a UK cash flow intelligence platform.

Your job: extract ALL financial information from documents uploaded by small businesses.

Document quality warning: These are REAL SME documents. Expect:
- Handwritten invoices and cheques
- Blurry or poorly-lit phone photos
- Faded receipts
- Non-standard layouts and formats
- Mixed languages (businesses may trade internationally)
- Currency symbols: £, €, $, د.إ (AED), ₺ (TRY), ﷼ (SAR)

Rules:
1. Extract everything you can see — partial data is better than no data.
2. For dates, normalise to YYYY-MM-DD format if possible. If only partial date visible, extract what's there.
3. For amounts, extract the numeric value. Note currency from symbol or context.
4. confidence_score: your honest 0.0–1.0 assessment of extraction quality.
   - 0.9+: clear, legible, all key fields extracted
   - 0.7–0.9: most fields extracted, one or two unclear
   - 0.5–0.7: significant uncertainty, handwritten or poor quality
   - <0.5: very low quality, many fields missing or guessed
5. confidence_notes: briefly explain what was unclear (e.g. "amount partially obscured", "date handwritten and ambiguous")
6. Never invent data. Leave fields empty string/null if genuinely unreadable.
7. For UK invoices: look for VAT number (format: GB + 9 digits), company number.
"""


# ── Main extraction function ───────────────────────────────────────────────


@dataclass
class ExtractionResult:
    data: dict
    schema_type: str
    tier_used: int
    tokens_used: int
    confidence_score: float


def extract_document(
    file_bytes: bytes,
    mime_type: str,
    document_type: str,
) -> ExtractionResult:
    """
    Main entry point. Runs the 4-tier pipeline and returns structured extraction.
    """
    schema_class = SCHEMA_MAP.get(document_type, InvoiceExtraction)
    client = Anthropic()

    # Tier 1: PDF text extraction (free)
    if 'pdf' in mime_type.lower():
        text = _extract_pdf_text(file_bytes)
        if text and len(text.strip()) > 50:
            logger.info('Doc extraction tier 1: PDF text extracted (%d chars)', len(text))
            result = _extract_with_text(client, text, document_type, schema_class, HAIKU_MODEL)
            if result.confidence_score >= TIER2_CONFIDENCE_THRESHOLD:
                return ExtractionResult(
                    data=result.data,
                    schema_type=document_type,
                    tier_used=1,
                    tokens_used=result.tokens_used,
                    confidence_score=result.confidence_score,
                )
            # Low confidence from text → convert PDF to image and try vision
            logger.info('Tier 1 low confidence (%.2f), escalating to vision', result.confidence_score)
            file_bytes = _pdf_to_image_bytes(file_bytes)
            mime_type = 'image/jpeg'

    # Tier 2: Haiku vision on (preprocessed) image
    preprocessed = _preprocess(file_bytes, mime_type)
    result = _extract_with_vision(client, preprocessed, mime_type, document_type, schema_class, HAIKU_MODEL)
    logger.info('Doc extraction tier 2/3: Haiku vision confidence=%.2f tokens=%d',
                result.confidence_score, result.tokens_used)

    if result.confidence_score >= TIER3_CONFIDENCE_THRESHOLD:
        return ExtractionResult(
            data=result.data,
            schema_type=document_type,
            tier_used=3,
            tokens_used=result.tokens_used,
            confidence_score=result.confidence_score,
        )

    # Tier 4: Sonnet — last resort for handwritten / very poor quality
    logger.info('Escalating to Sonnet (confidence %.2f < threshold)', result.confidence_score)
    haiku_tokens = result.tokens_used
    result = _extract_with_vision(client, preprocessed, mime_type, document_type, schema_class, SONNET_MODEL)
    logger.info('Doc extraction tier 4: Sonnet confidence=%.2f tokens=%d', result.confidence_score, result.tokens_used)

    return ExtractionResult(
        data=result.data,
        schema_type=document_type,
        tier_used=4,
        tokens_used=haiku_tokens + result.tokens_used,
        confidence_score=result.confidence_score,
    )


# ── Internal helpers ───────────────────────────────────────────────────────


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF using pdfplumber. Returns empty string if fails."""
    try:
        text_parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return '\n'.join(text_parts)
    except Exception as exc:
        logger.debug('pdfplumber extraction failed: %s', exc)
        return ''


def _pdf_to_image_bytes(pdf_bytes: bytes) -> bytes:
    """Convert first page of PDF to JPEG image bytes."""
    from pdf2image import convert_from_bytes
    images = convert_from_bytes(pdf_bytes, dpi=200, first_page=1, last_page=1)
    if not images:
        raise RuntimeError('pdf2image returned no pages')
    buf = io.BytesIO()
    images[0].save(buf, format='JPEG', quality=88)
    return buf.getvalue()


def _preprocess(file_bytes: bytes, mime_type: str) -> bytes:
    """Run image preprocessing pipeline."""
    from .preprocessing import preprocess_image
    result = preprocess_image(file_bytes, mime_type)
    return result.image_bytes


@dataclass
class _RawResult:
    data: dict
    tokens_used: int
    confidence_score: float


def _extract_with_text(
    client: Anthropic,
    text: str,
    document_type: str,
    schema_class: type[BaseModel],
    model: str,
) -> _RawResult:
    """Call Claude with text-only input."""
    user_message = (
        f'Extract all financial data from this {document_type} document.\n\n'
        f'<document_text>\n{text}\n</document_text>'
    )
    return _call_claude(client, user_message, schema_class, model)


def _extract_with_vision(
    client: Anthropic,
    image_bytes: bytes,
    mime_type: str,
    document_type: str,
    schema_class: type[BaseModel],
    model: str,
) -> _RawResult:
    """Call Claude with image input."""
    b64_image = base64.standard_b64encode(image_bytes).decode()
    message_content = [
        {
            'type': 'image',
            'source': {
                'type': 'base64',
                'media_type': 'image/jpeg',
                'data': b64_image,
            },
        },
        {
            'type': 'text',
            'text': f'Extract all financial data from this {document_type} document image.',
        },
    ]
    return _call_claude(client, message_content, schema_class, model)


def _call_claude(
    client: Anthropic,
    user_content,
    schema_class: type[BaseModel],
    model: str,
) -> _RawResult:
    """Make the Claude API call with structured output."""
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': user_content}],
        tools=[{
            'name': 'extract_document_data',
            'description': 'Extract structured financial data from the document',
            'input_schema': schema_class.model_json_schema(),
        }],
        tool_choice={'type': 'tool', 'name': 'extract_document_data'},
    )

    tokens_used = response.usage.input_tokens + response.usage.output_tokens

    # Find the tool use block
    tool_block = next(
        (block for block in response.content if block.type == 'tool_use'),
        None,
    )
    if tool_block is None:
        raise RuntimeError('Claude did not return a tool_use block')

    raw_data = tool_block.input
    confidence = float(raw_data.get('confidence_score', 0.0))

    return _RawResult(data=raw_data, tokens_used=tokens_used, confidence_score=confidence)
