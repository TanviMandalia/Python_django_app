"""
File Security and Upload Validation Module for Hospital Management System.

Enforces strict defense-in-depth security for all uploaded files:
1. Strict extension whitelisting (never trust client filename alone).
2. Explicit blacklist blocking of executable/script extensions (.php, .exe, .sh, .html, .svg, etc.).
3. Maximum file size constraints (memory-exhaustion & DoS defense).
4. Magic byte signature verification and Pillow deep-inspection for images.
5. Directory path traversal protection (sanitized storage filenames).
6. Safe HTML sanitization for inbound email and notes (XSS protection).
"""

import os
import re
import uuid
import logging
from io import BytesIO
from django.core.exceptions import ValidationError
from PIL import Image

logger = logging.getLogger(__name__)

# Dangerous extensions that must never be accepted under any circumstances
DANGEROUS_EXTENSIONS = frozenset({
    ".php", ".phtml", ".php3", ".php4", ".php5", ".phps", ".pht",
    ".exe", ".bat", ".cmd", ".com", ".sh", ".bash", ".zsh",
    ".js", ".mjs", ".vbs", ".vbe", ".wsf", ".wsh",
    ".html", ".htm", ".xhtml", ".shtml", ".svg", ".svgz",
    ".swf", ".jar", ".war", ".jsp", ".asp", ".aspx", ".cgi", ".pl",
    ".py", ".pyc", ".pyo", ".rb", ".dll", ".so", ".dylib", ".bin",
})

ALLOWED_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
ALLOWED_EXCEL_EXTENSIONS = frozenset({".xlsx"})
ALLOWED_ATTACHMENT_EXTENSIONS = frozenset({".pdf", ".docx", ".xlsx", ".jpg", ".jpeg", ".png", ".webp"})

IMAGE_MAGIC_SIGNATURES = {
    "JPEG": b"\xff\xd8\xff",
    "PNG": b"\x89PNG\r\n\x1a\n",
    "WEBP": b"RIFF",
}

ZIP_MAGIC_SIGNATURE = b"PK\x03\x04"
PDF_MAGIC_SIGNATURE = b"%PDF"


def sanitize_upload_filename(filename):
    """
    Sanitize an uploaded filename to prevent directory traversal and filesystem attacks.
    Returns a safe, unique filename preserving only valid alphanumeric and dot chars.
    """
    if not filename:
        return f"file_{uuid.uuid4().hex[:8]}.bin"

    # Strip path separators and traversal attempts
    cleaned = os.path.basename(filename).replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", cleaned)  # strip control characters
    cleaned = re.sub(r"\.\.+", ".", cleaned)  # eliminate multiple dots

    base, ext = os.path.splitext(cleaned)
    ext = ext.lower().strip()
    safe_base = re.sub(r"[^a-zA-Z0-9_\-]", "_", base)[:40].strip("_") or "upload"

    unique_id = uuid.uuid4().hex[:8]
    return f"{safe_base}_{unique_id}{ext}"


def validate_image_file(uploaded_file, max_size_mb=5, field_name="Image"):
    """
    Validate that an uploaded file is a genuine, safe image (JPEG, PNG, WebP).
    Verifies:
      - File size limit (default 5MB)
      - Extension whitelist & dangerous extension rejection
      - Magic byte signature
      - Pillow image integrity parsing
    """
    if not uploaded_file:
        return True

    # 1. Size verification
    max_bytes = max_size_mb * 1024 * 1024
    if uploaded_file.size > max_bytes:
        raise ValidationError(f"{field_name} file size cannot exceed {max_size_mb}MB.")

    # 2. Extension check
    filename = uploaded_file.name or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext in DANGEROUS_EXTENSIONS:
        raise ValidationError(f"Dangerous or executable file extension '{ext}' is prohibited.")

    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(f"Invalid image format. Allowed formats: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}.")

    # 3. Magic byte check
    uploaded_file.seek(0)
    header = uploaded_file.read(32)
    uploaded_file.seek(0)

    if not header:
        raise ValidationError("Uploaded file is empty.")

    is_valid_magic = False
    if header.startswith(IMAGE_MAGIC_SIGNATURES["JPEG"]):
        is_valid_magic = True
    elif header.startswith(IMAGE_MAGIC_SIGNATURES["PNG"]):
        is_valid_magic = True
    elif header.startswith(IMAGE_MAGIC_SIGNATURES["WEBP"]) and len(header) >= 12 and header[8:12] == b"WEBP":
        is_valid_magic = True

    if not is_valid_magic:
        raise ValidationError("File signature does not match a valid image (JPEG, PNG, WebP).")

    # 4. Pillow structure and format verification
    try:
        image_data = uploaded_file.read()
        uploaded_file.seek(0)
        img = Image.open(BytesIO(image_data))
        img.verify()
        if img.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValidationError(f"Disallowed image format: {img.format}")
    except Exception as exc:
        raise ValidationError(f"Invalid or corrupted image file: {str(exc)}")
    finally:
        uploaded_file.seek(0)

    return True


def validate_excel_file(uploaded_file, max_size_mb=10, field_name="Excel file"):
    """
    Validate that an uploaded file is a safe, valid Excel workbook (.xlsx).
    """
    if not uploaded_file:
        raise ValidationError(f"{field_name} is required.")

    max_bytes = max_size_mb * 1024 * 1024
    if uploaded_file.size > max_bytes:
        raise ValidationError(f"{field_name} file size cannot exceed {max_size_mb}MB.")

    filename = uploaded_file.name or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext in DANGEROUS_EXTENSIONS:
        raise ValidationError(f"Dangerous file extension '{ext}' is prohibited.")

    if ext not in ALLOWED_EXCEL_EXTENSIONS:
        raise ValidationError(f"Invalid file type. Please upload a valid Excel file ({', '.join(ALLOWED_EXCEL_EXTENSIONS)}).")

    uploaded_file.seek(0)
    header = uploaded_file.read(4)
    uploaded_file.seek(0)

    if header != ZIP_MAGIC_SIGNATURE:
        raise ValidationError("Uploaded file is not a valid OpenXML Excel spreadsheet.")

    return True


def validate_attachment_file(uploaded_file, max_size_mb=10, allowed_extensions=None):
    """
    Validate general document/medical attachments (PDF, DOCX, XLSX, Images).
    """
    if not uploaded_file:
        return True

    allowed = allowed_extensions or ALLOWED_ATTACHMENT_EXTENSIONS
    max_bytes = max_size_mb * 1024 * 1024

    if uploaded_file.size > max_bytes:
        raise ValidationError(f"Attachment cannot exceed {max_size_mb}MB.")

    filename = uploaded_file.name or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext in DANGEROUS_EXTENSIONS:
        raise ValidationError(f"Dangerous file extension '{ext}' is prohibited.")

    if ext not in allowed:
        raise ValidationError(f"File type '{ext}' is not permitted. Allowed: {', '.join(sorted(allowed))}")

    # Inspect magic bytes
    uploaded_file.seek(0)
    header = uploaded_file.read(8)
    uploaded_file.seek(0)

    if ext == ".pdf" and not header.startswith(PDF_MAGIC_SIGNATURE):
        raise ValidationError("Invalid PDF file signature.")
    elif ext in {".docx", ".xlsx"} and not header.startswith(ZIP_MAGIC_SIGNATURE):
        raise ValidationError("Invalid Office document signature.")
    elif ext in ALLOWED_IMAGE_EXTENSIONS:
        validate_image_file(uploaded_file, max_size_mb=max_size_mb)

    return True


def sanitize_html_content(raw_html):
    """
    Sanitize untrusted incoming HTML (e.g. from inbound emails or patient messages)
    to prevent Stored XSS, script injection, iframe hijacking, and event handler attacks.
    """
    if not raw_html:
        return ""

    content = str(raw_html)

    # 1. Remove dangerous executable tags completely
    dangerous_tags = [
        r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
        r"<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>",
        r"<object\b[^<]*(?:(?!<\/object>)<[^<]*)*<\/object>",
        r"<embed\b[^<]*(?:(?!<\/embed>)<[^<]*)*<\/embed>",
        r"<applet\b[^<]*(?:(?!<\/applet>)<[^<]*)*<\/applet>",
        r"<meta\b[^>]*>",
        r"<link\b[^>]*>",
        r"<form\b[^<]*(?:(?!<\/form>)<[^<]*)*<\/form>",
    ]
    for pattern in dangerous_tags:
        content = re.sub(pattern, "", content, flags=re.IGNORECASE)

    # 2. Strip javascript: and vbscript: URIs
    content = re.sub(r'href\s*=\s*["\']\s*(?:javascript|vbscript|data):[^"\']*["\']', 'href="#"', content, flags=re.IGNORECASE)
    content = re.sub(r'src\s*=\s*["\']\s*(?:javascript|vbscript):[^"\']*["\']', 'src=""', content, flags=re.IGNORECASE)

    # 3. Strip all inline event handlers (onabort, onclick, onerror, onload, onmouseover, etc.)
    content = re.sub(r'\s+on[a-zA-Z]+\s*=\s*["\'][^"\']*["\']', "", content, flags=re.IGNORECASE)
    content = re.sub(r'\s+on[a-zA-Z]+\s*=\s*[^>\s]+', "", content, flags=re.IGNORECASE)

    return content.strip()
