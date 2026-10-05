import io
from PIL import Image
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from core.file_security import (
    validate_image_file,
    validate_excel_file,
    validate_attachment_file,
    sanitize_upload_filename,
    sanitize_html_content,
    DANGEROUS_EXTENSIONS,
)


class FileSecurityTests(TestCase):
    def setUp(self):
        # Generate valid minimal JPEG image
        img_io = io.BytesIO()
        img = Image.new("RGB", (64, 64), color="blue")
        img.save(img_io, format="JPEG")
        self.valid_jpeg_bytes = img_io.getvalue()

        # Generate valid minimal PNG image
        png_io = io.BytesIO()
        png_img = Image.new("RGBA", (32, 32), color="red")
        png_img.save(png_io, format="PNG")
        self.valid_png_bytes = png_io.getvalue()

        # Minimal valid ZIP/OpenXML magic bytes
        self.valid_zip_bytes = b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"\x00" * 50

    def test_valid_jpeg_and_png_allowed(self):
        f_jpg = SimpleUploadedFile("avatar.jpg", self.valid_jpeg_bytes, content_type="image/jpeg")
        f_png = SimpleUploadedFile("avatar.png", self.valid_png_bytes, content_type="image/png")
        self.assertTrue(validate_image_file(f_jpg))
        self.assertTrue(validate_image_file(f_png))

    def test_dangerous_executable_extensions_rejected(self):
        dangerous_list = [".exe", ".bat", ".sh", ".php", ".phtml", ".js", ".html", ".svg", ".py"]
        for ext in dangerous_list:
            bad_file = SimpleUploadedFile(f"malware{ext}", b"echo 'attack'", content_type="application/octet-stream")
            with self.assertRaises(ValidationError) as ctx:
                validate_image_file(bad_file)
            self.assertIn("prohibited", str(ctx.exception).lower())

    def test_spoofed_extension_magic_bytes_mismatch_rejected(self):
        # A text file renamed to .jpg
        spoofed = SimpleUploadedFile("photo.jpg", b"This is not a real image header", content_type="image/jpeg")
        with self.assertRaises(ValidationError) as ctx:
            validate_image_file(spoofed)
        self.assertIn("signature", str(ctx.exception).lower())

    def test_image_file_size_limit_exceeded(self):
        # 6MB dummy file
        huge_bytes = self.valid_jpeg_bytes + b"\x00" * (6 * 1024 * 1024)
        huge_file = SimpleUploadedFile("huge.jpg", huge_bytes, content_type="image/jpeg")
        with self.assertRaises(ValidationError) as ctx:
            validate_image_file(huge_file, max_size_mb=5)
        self.assertIn("exceed 5mb", str(ctx.exception).lower())

    def test_excel_validation_valid_and_invalid(self):
        valid_excel = SimpleUploadedFile("data.xlsx", self.valid_zip_bytes, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(validate_excel_file(valid_excel))

        fake_excel = SimpleUploadedFile("fake.xlsx", b"not a zip file", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with self.assertRaises(ValidationError):
            validate_excel_file(fake_excel)

        wrong_ext = SimpleUploadedFile("script.py", self.valid_zip_bytes, content_type="text/plain")
        with self.assertRaises(ValidationError):
            validate_excel_file(wrong_ext)

    def test_attachment_validation(self):
        # PDF validation
        valid_pdf = SimpleUploadedFile("report.pdf", b"%PDF-1.4\n%test\n", content_type="application/pdf")
        self.assertTrue(validate_attachment_file(valid_pdf))

        invalid_pdf = SimpleUploadedFile("corrupt.pdf", b"NOTAPDF", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_attachment_file(invalid_pdf)

    def test_sanitize_upload_filename_traversal_prevention(self):
        traversal_attempts = [
            ("../../etc/passwd.jpg", ".jpg"),
            ("..\\..\\windows\\system32\\cmd.exe", ".exe"),
            ("normal_doc...pdf", ".pdf"),
            ("hello\x00world.png", ".png"),
            ("my profile (photo) 2026!.jpeg", ".jpeg"),
        ]
        for malicious_name, expected_ext in traversal_attempts:
            safe_name = sanitize_upload_filename(malicious_name)
            self.assertNotIn("..", safe_name)
            self.assertNotIn("/", safe_name)
            self.assertNotIn("\\", safe_name)
            self.assertNotIn("\x00", safe_name)
            self.assertTrue(safe_name.endswith(expected_ext))

    def test_sanitize_html_content_xss_protection(self):
        dirty_html = (
            "<p>Hello Patient</p>"
            "<script>alert('XSS')</script>"
            "<iframe src='http://evil.com'></iframe>"
            "<a href='javascript:alert(1)' onclick='bad()'>Click Me</a>"
            "<img src='photo.jpg' onerror='stealCookie()'>"
        )
        clean = sanitize_html_content(dirty_html)
        self.assertNotIn("<script", clean.lower())
        self.assertNotIn("<iframe", clean.lower())
        self.assertNotIn("javascript:", clean.lower())
        self.assertNotIn("onclick", clean.lower())
        self.assertNotIn("onerror", clean.lower())
        self.assertIn("<p>Hello Patient</p>", clean)
