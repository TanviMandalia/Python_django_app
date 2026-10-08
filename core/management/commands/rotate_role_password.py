"""
Management command: rotate_role_password
Safely rotates an existing user account password using Django's supported
password-setting mechanisms (PBKDF2/Argon2/bcrypt hashing).

Supports:
  1. Interactive secure prompt (getpass)
  2. Standard input (--stdin) for piping from secret managers (e.g., Vault, AWS Secrets Manager)
  3. Named environment variable (--env-var)
  4. Explicit argument (--password, recommended only for non-shell automated scripts)

Never outputs or logs the password.
Enforces Django password validators by default.
"""

import getpass
import os
import sys
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = "Safely rotate a user's password using Django's standard hashing mechanisms."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            "-u",
            type=str,
            required=True,
            help="Username of the account whose password is to be rotated.",
        )
        parser.add_argument(
            "--password",
            "-p",
            type=str,
            default=None,
            help="New password (avoid on shared systems to prevent bash history exposure).",
        )
        parser.add_argument(
            "--env-var",
            type=str,
            default=None,
            help="Name of an environment variable containing the new password.",
        )
        parser.add_argument(
            "--stdin",
            action="store_true",
            help="Read the new password from standard input (pipe-friendly).",
        )
        parser.add_argument(
            "--skip-validation",
            action="store_true",
            help="Bypass Django AUTH_PASSWORD_VALIDATORS checks (not recommended).",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        new_password = None

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"User with username '{username}' does not exist.")

        # Determine password source
        if options["stdin"]:
            new_password = sys.stdin.readline().rstrip("\r\n")
            if not new_password:
                raise CommandError("No password received from standard input.")
        elif options["env_var"]:
            var_name = options["env_var"].strip()
            new_password = os.getenv(var_name)
            if not new_password:
                raise CommandError(f"Environment variable '{var_name}' is unset or empty.")
        elif options["password"]:
            new_password = options["password"]
        else:
            # Interactive prompt
            if not sys.stdin.isatty():
                raise CommandError(
                    "Password must be supplied via --stdin, --env-var, or --password in non-interactive environments."
                )
            pwd1 = getpass.getpass(f"Enter new password for user '{username}': ")
            pwd2 = getpass.getpass("Confirm new password: ")
            if pwd1 != pwd2:
                raise CommandError("Passwords do not match.")
            new_password = pwd1

        # Validation
        if not options["skip_validation"]:
            try:
                validate_password(new_password, user=user)
            except ValidationError as exc:
                raise CommandError(f"Password validation failed: {'; '.join(exc.messages)}")

        # Safe update using Django set_password
        user.set_password(new_password)
        user.save(update_fields=["password"])

        # Prevent password remaining in local scope
        del new_password

        # Retrieve role summary if available
        role_desc = "Standard User"
        if user.is_superuser:
            role_desc = "Superuser / Platform Admin"
        elif hasattr(user, "user_roles"):
            roles = [ur.role.name for ur in user.user_roles.all() if ur.role]
            if roles:
                role_desc = ", ".join(roles)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully rotated password for user '{username}' (Role: {role_desc})."
            )
        )
