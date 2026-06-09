"""
Storage backend abstraction for uploaded documents.

Supports: local filesystem, S3-compatible (AWS/R2/DigitalOcean), Supabase Storage.
Backend chosen per-org via DocumentStorageSettings.
"""

import logging
import os
import uuid
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


def save_upload(
    org_id: str,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    storage_settings,
) -> str:
    """
    Save uploaded file using the org's configured storage backend.
    Returns the file_path string to store in Document.file_path.
    """
    backend = getattr(storage_settings, 'backend', 'local') if storage_settings else 'local'
    ext = Path(filename).suffix.lower() or _mime_to_ext(mime_type)
    unique_name = f'{uuid.uuid4()}{ext}'
    relative_path = f'documents/{org_id}/{unique_name}'

    if backend == 's3':
        return _save_s3(file_bytes, relative_path, mime_type, storage_settings)
    if backend == 'supabase':
        return _save_supabase(file_bytes, relative_path, mime_type, storage_settings)

    return _save_local(file_bytes, relative_path)


def load_file(file_path: str, storage_settings) -> bytes:
    """Load file bytes from wherever it was stored."""
    backend = getattr(storage_settings, 'backend', 'local') if storage_settings else 'local'

    if backend == 's3':
        return _load_s3(file_path, storage_settings)
    if backend == 'supabase':
        return _load_supabase(file_path, storage_settings)

    return _load_local(file_path)


def _save_local(file_bytes: bytes, relative_path: str) -> str:
    media_root = getattr(settings, 'MEDIA_ROOT', '/app/media')
    full_path = Path(media_root) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(file_bytes)
    logger.debug('Saved file locally: %s', full_path)
    return f'local:{relative_path}'


def _load_local(file_path: str) -> bytes:
    relative = file_path.removeprefix('local:')
    media_root = getattr(settings, 'MEDIA_ROOT', '/app/media')
    return (Path(media_root) / relative).read_bytes()


def _save_s3(file_bytes: bytes, key: str, mime_type: str, cfg) -> str:
    import boto3
    from core.utils.encryption import decrypt

    session = boto3.client(
        's3',
        aws_access_key_id=decrypt(cfg.s3_access_key_encrypted),
        aws_secret_access_key=decrypt(cfg.s3_secret_key_encrypted),
        region_name=cfg.s3_region or None,
        endpoint_url=cfg.s3_endpoint_url or None,
    )
    session.put_object(
        Bucket=cfg.s3_bucket,
        Key=key,
        Body=file_bytes,
        ContentType=mime_type,
        ServerSideEncryption='AES256',
    )
    logger.debug('Saved file to S3: %s/%s', cfg.s3_bucket, key)
    return f's3:{cfg.s3_bucket}/{key}'


def _load_s3(file_path: str, cfg) -> bytes:
    import boto3
    from core.utils.encryption import decrypt

    parts = file_path.removeprefix('s3:').split('/', 1)
    bucket, key = parts[0], parts[1]

    client = boto3.client(
        's3',
        aws_access_key_id=decrypt(cfg.s3_access_key_encrypted),
        aws_secret_access_key=decrypt(cfg.s3_secret_key_encrypted),
        region_name=cfg.s3_region or None,
        endpoint_url=cfg.s3_endpoint_url or None,
    )
    response = client.get_object(Bucket=bucket, Key=key)
    return response['Body'].read()


def _save_supabase(file_bytes: bytes, key: str, mime_type: str, cfg) -> str:
    import httpx
    from core.utils.encryption import decrypt

    supabase_key = decrypt(cfg.supabase_key_encrypted)
    url = f'{cfg.supabase_url}/storage/v1/object/{cfg.supabase_bucket}/{key}'
    resp = httpx.put(
        url,
        content=file_bytes,
        headers={
            'Authorization': f'Bearer {supabase_key}',
            'Content-Type': mime_type,
        },
    )
    resp.raise_for_status()
    logger.debug('Saved file to Supabase: %s/%s', cfg.supabase_bucket, key)
    return f'supabase:{cfg.supabase_bucket}/{key}'


def _load_supabase(file_path: str, cfg) -> bytes:
    import httpx
    from core.utils.encryption import decrypt

    supabase_key = decrypt(cfg.supabase_key_encrypted)
    parts = file_path.removeprefix('supabase:').split('/', 1)
    bucket, key = parts[0], parts[1]
    url = f'{cfg.supabase_url}/storage/v1/object/{bucket}/{key}'
    resp = httpx.get(url, headers={'Authorization': f'Bearer {supabase_key}'})
    resp.raise_for_status()
    return resp.content


def _mime_to_ext(mime_type: str) -> str:
    mapping = {
        'application/pdf': '.pdf',
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/png': '.png',
        'image/webp': '.webp',
        'image/heic': '.heic',
        'image/tiff': '.tiff',
    }
    return mapping.get(mime_type.lower(), '.bin')
