import os
import sys
from pathlib import Path
import django
from django.template.loader import get_template

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings.dev")
django.setup()

tmpl_dir = Path("templates")
all_templates = list(tmpl_dir.rglob("*.html"))
print(f"Checking {len(all_templates)} HTML templates across repository...")

errors = []
for p in all_templates:
    rel = p.relative_to(tmpl_dir).as_posix()
    try:
        get_template(rel)
    except Exception as exc:
        errors.append((rel, str(exc)))

if errors:
    print(f"Found {len(errors)} template errors:")
    for path, err in errors:
        print(f"  [ERROR] {path}: {err}")
else:
    print(f"SUCCESS: All {len(all_templates)} templates compiled and parsed with ZERO errors!")
