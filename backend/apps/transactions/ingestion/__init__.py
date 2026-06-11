"""Source-agnostic ingestion: one adapter contract for every data source.

The blueprint (§5) defines an ``IngestionSource`` contract —
connect / fetch / normalise / dedupe / persist — so that bank feeds,
accounting APIs, documents, CSV import, and manual entry all flow through the
same pipeline into a single normalised ``Transaction`` shape. Connectors built
in much later phases plug in here without touching the persistence logic.
"""
from .base import (
    IngestionResult,
    IngestionSource,
    NormalizedTransaction,
)
from .csv_import import CsvImportSource
from .manual import ManualEntrySource

__all__ = [
    'IngestionResult',
    'IngestionSource',
    'NormalizedTransaction',
    'CsvImportSource',
    'ManualEntrySource',
]
