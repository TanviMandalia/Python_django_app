import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings.dev')
django.setup()

from django.test import Client
from django.urls import reverse

client = Client()

roles_to_test = [
    ("Super Admin", "super_admin_core", "x0KX#KbokqhqY2JyI8Edr4UR", "/super-admin/"),
    ("Clinic Admin", "clinic_admin_main", "f71jQiKG%*hBAeT6DN3tE7XH", "/admin-dashboard/"),
    ("Staff", "physio_staff_pro", "U#NQSzxIvg5axhMHu1u!7V$S", "/staff-dashboard/"),
    ("Patient", "patient_user_primary", "AzzjrOB5eUuugbt$8U8fOHPx", "/client-dashboard/"),
]

from django.core.cache import cache

for role_name, username, password, expected_dest in roles_to_test:
    cache.clear()
    c = Client()
    resp = c.post(reverse('login'), {'username': username, 'password': password}, follow=False)
    if resp.status_code == 302:
        print(f"[{role_name}] User: {username} -> Status: {resp.status_code}, Redirect URL: {resp.url}")
    else:
        print(f"[{role_name}] User: {username} -> Status: {resp.status_code} (FAILED)")
    assert resp.status_code == 302, f"Expected 302, got {resp.status_code}"
    assert expected_dest in resp.url, f"Expected {expected_dest} in {resp.url}"

print("ALL 4 ROLES REDIRECT PROPERLY!")
