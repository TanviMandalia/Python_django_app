"""
Django System Checks for Hospital Management System.
Validates production readiness including SMTP configuration.
"""
from django.core.checks import Error, Warning, register, Tags
from django.conf import settings


@register(Tags.compatibility)
def check_smtp_configuration(app_configs, **kwargs):
    """
    Validate that required SMTP email configuration is present and non-conflicting.
    Does not expose sensitive credentials in messages.
    """
    errors = []
    backend = getattr(settings, "EMAIL_BACKEND", "")

    # Only validate credentials when using SMTP backend
    if backend == "django.core.mail.backends.smtp.EmailBackend":
        host = getattr(settings, "EMAIL_HOST", "")
        port = getattr(settings, "EMAIL_PORT", None)
        user = getattr(settings, "EMAIL_HOST_USER", "")
        password = getattr(settings, "EMAIL_HOST_PASSWORD", "")
        use_tls = getattr(settings, "EMAIL_USE_TLS", False)
        use_ssl = getattr(settings, "EMAIL_USE_SSL", False)
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")
        debug = getattr(settings, "DEBUG", False)

        missing_fields = []
        if not host:
            missing_fields.append("EMAIL_HOST")
        if not port:
            missing_fields.append("EMAIL_PORT")
        if not user:
            missing_fields.append("EMAIL_HOST_USER")
        if not password:
            missing_fields.append("EMAIL_HOST_PASSWORD")
        if not from_email:
            missing_fields.append("DEFAULT_FROM_EMAIL")

        if missing_fields:
            msg = (
                f"Incomplete SMTP configuration. Missing required setting(s): {', '.join(missing_fields)}. "
                "Ensure environment variables are populated for SMTP delivery."
            )
            hint = "Set EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, and DEFAULT_FROM_EMAIL in your environment."
            if debug:
                errors.append(
                    Warning(
                        msg,
                        hint=hint + " Or set DEV_EMAIL_CONSOLE=true or EMAIL_BACKEND to console backend in dev.",
                        id="core.W001",
                    )
                )
            else:
                errors.append(
                    Error(
                        msg,
                        hint=hint,
                        id="core.E001",
                    )
                )

        if use_tls and use_ssl:
            errors.append(
                Error(
                    "Both EMAIL_USE_TLS and EMAIL_USE_SSL are enabled simultaneously. Choose either TLS (port 587) or SSL (port 465).",
                    hint="Set EMAIL_USE_TLS=True and EMAIL_USE_SSL=False for standard STARTTLS.",
                    id="core.E002",
                )
            )

    # Validate credentials when using Resend HTTPS API backend
    elif backend == "core.email_backend.ResendEmailBackend":
        resend_key = getattr(settings, "RESEND_API_KEY", "")
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")
        debug = getattr(settings, "DEBUG", False)

        missing_fields = []
        if not resend_key:
            missing_fields.append("RESEND_API_KEY")
        if not from_email:
            missing_fields.append("DEFAULT_FROM_EMAIL")

        if missing_fields:
            msg = (
                f"Incomplete Resend HTTPS email configuration. Missing required setting(s): {', '.join(missing_fields)}. "
                "Ensure environment variables are populated for HTTPS API email delivery."
            )
            hint = "Set RESEND_API_KEY and DEFAULT_FROM_EMAIL (e.g. 'Clinic <onboarding@resend.dev>') in environment variables."
            if debug:
                errors.append(
                    Warning(
                        msg,
                        hint=hint,
                        id="core.W003",
                    )
                )
            else:
                errors.append(
                    Error(
                        msg,
                        hint=hint,
                        id="core.E003",
                    )
                )

    return errors
