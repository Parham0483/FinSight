"""
Document preprocessing pipeline.

Runs BEFORE any API call — zero tokens, zero cost.
Handles the full spectrum of SME document quality:
  - Photo taken at an angle (perspective correction)
  - Rotated scan (deskew)
  - Low contrast / faded ink (CLAHE enhancement)
  - Noisy background / shadows (denoising)
  - Very small images (upscaling)
  - EXIF orientation issues (auto-rotate)
"""

import io
import math
import logging
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, ExifTags

logger = logging.getLogger(__name__)

MAX_DIMENSION = 2048   # cap before sending to vision API
MIN_DIMENSION = 800    # upscale if smaller
JPEG_QUALITY = 88


@dataclass(frozen=True)
class PreprocessResult:
    image_bytes: bytes
    mime_type: str
    width: int
    height: int
    operations_applied: list[str]


def preprocess_image(raw_bytes: bytes, source_mime: str = 'image/jpeg') -> PreprocessResult:
    """
    Full preprocessing pipeline for a document image.
    Returns enhanced image bytes ready for vision API.
    """
    operations: list[str] = []

    # 1. Load via Pillow first (handles all formats + EXIF)
    pil_image = _load_and_fix_orientation(raw_bytes, operations)

    # 2. Convert to numpy for OpenCV processing
    img_array = np.array(pil_image.convert('RGB'))
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

    # 3. Upscale if too small (helps vision models read text)
    img_bgr, operations = _upscale_if_needed(img_bgr, operations)

    # 4. Perspective correction — fix angled photos of documents
    img_bgr, operations = _correct_perspective(img_bgr, operations)

    # 5. Deskew — fix rotated scans
    img_bgr, operations = _deskew(img_bgr, operations)

    # 6. Denoise — remove background noise, shadows
    img_bgr, operations = _denoise(img_bgr, operations)

    # 7. Contrast enhancement — make faded text readable
    img_bgr, operations = _enhance_contrast(img_bgr, operations)

    # 8. Cap resolution to avoid excessive token usage
    img_bgr, operations = _cap_resolution(img_bgr, operations)

    # 9. Convert back to JPEG bytes
    output_bytes = _to_jpeg_bytes(img_bgr, JPEG_QUALITY)
    h, w = img_bgr.shape[:2]

    logger.debug('Preprocessing complete: %dx%d, ops=%s', w, h, operations)

    return PreprocessResult(
        image_bytes=output_bytes,
        mime_type='image/jpeg',
        width=w,
        height=h,
        operations_applied=operations,
    )


def _load_and_fix_orientation(raw_bytes: bytes, operations: list[str]) -> Image.Image:
    """Load image and correct EXIF orientation (phone photos are often rotated)."""
    image = Image.open(io.BytesIO(raw_bytes))

    # Apply EXIF orientation
    try:
        image = ImageOps.exif_transpose(image)
        operations = [*operations, 'exif_orientation_fixed']
    except Exception:
        pass

    return image


def _upscale_if_needed(img: np.ndarray, operations: list[str]) -> tuple[np.ndarray, list[str]]:
    h, w = img.shape[:2]
    if min(h, w) < MIN_DIMENSION:
        scale = MIN_DIMENSION / min(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        return img, [*operations, f'upscaled_{w}x{h}_to_{new_w}x{new_h}']
    return img, operations


def _correct_perspective(img: np.ndarray, operations: list[str]) -> tuple[np.ndarray, list[str]]:
    """
    Detect document edges and apply perspective transform to straighten it.
    Only applies if a clear rectangular document boundary is found.
    Falls back gracefully if no clear boundary detected.
    """
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 150)

        # Dilate to close gaps in edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edged = cv2.dilate(edged, kernel, iterations=2)

        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img, operations

        # Find the largest contour — likely the document boundary
        largest = max(contours, key=cv2.contourArea)
        img_area = img.shape[0] * img.shape[1]

        # Only proceed if contour covers at least 20% of image
        if cv2.contourArea(largest) < img_area * 0.20:
            return img, operations

        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.02 * peri, True)

        # Need exactly 4 corners for perspective transform
        if len(approx) != 4:
            return img, operations

        pts = approx.reshape(4, 2).astype(np.float32)
        pts = _order_points(pts)
        warped = _four_point_transform(img, pts)

        return warped, [*operations, 'perspective_corrected']

    except Exception as exc:
        logger.debug('Perspective correction skipped: %s', exc)
        return img, operations


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order corner points: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left
    rect[2] = pts[np.argmax(s)]   # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect


def _four_point_transform(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    (tl, tr, br, bl) = pts
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(int(width_a), int(width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(int(height_a), int(height_b))

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(pts, dst)
    return cv2.warpPerspective(img, M, (max_width, max_height))


def _deskew(img: np.ndarray, operations: list[str]) -> tuple[np.ndarray, list[str]]:
    """
    Detect and correct document rotation (e.g. scanner placed at slight angle).
    Only corrects if rotation is between 1–45 degrees.
    """
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 100:
            return img, operations

        angle = cv2.minAreaRect(coords)[-1]

        # minAreaRect returns angle in [-90, 0); convert to actual skew angle
        if angle < -45:
            angle = 90 + angle

        # Only correct if meaningfully skewed (>0.5°) but not too extreme (>45°)
        if not (0.5 < abs(angle) <= 45):
            return img, operations

        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)

        return rotated, [*operations, f'deskewed_{angle:.1f}deg']

    except Exception as exc:
        logger.debug('Deskew skipped: %s', exc)
        return img, operations


def _denoise(img: np.ndarray, operations: list[str]) -> tuple[np.ndarray, list[str]]:
    """
    Remove noise, grain, and shadows using Non-local Means Denoising.
    Conservative settings to avoid blurring text.
    """
    try:
        denoised = cv2.fastNlMeansDenoisingColored(img, None, h=6, hColor=6, templateWindowSize=7, searchWindowSize=21)
        return denoised, [*operations, 'denoised']
    except Exception as exc:
        logger.debug('Denoising skipped: %s', exc)
        return img, operations


def _enhance_contrast(img: np.ndarray, operations: list[str]) -> tuple[np.ndarray, list[str]]:
    """
    CLAHE (Contrast Limited Adaptive Histogram Equalization).
    Makes faded ink, low-contrast documents more readable without over-processing.
    Applied to L channel of LAB colour space to preserve colour balance.
    """
    try:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l_channel)

        enhanced_lab = cv2.merge([l_enhanced, a_channel, b_channel])
        enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

        return enhanced, [*operations, 'clahe_contrast']

    except Exception as exc:
        logger.debug('Contrast enhancement skipped: %s', exc)
        return img, operations


def _cap_resolution(img: np.ndarray, operations: list[str]) -> tuple[np.ndarray, list[str]]:
    """Resize down if either dimension exceeds MAX_DIMENSION. Reduces token usage."""
    h, w = img.shape[:2]
    if max(h, w) <= MAX_DIMENSION:
        return img, operations

    scale = MAX_DIMENSION / max(h, w)
    new_w = int(w * scale)
    new_h = int(h * scale)
    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return img, [*operations, f'resized_{w}x{h}_to_{new_w}x{new_h}']


def _to_jpeg_bytes(img: np.ndarray, quality: int) -> bytes:
    success, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise RuntimeError('Failed to encode image as JPEG')
    return buffer.tobytes()
