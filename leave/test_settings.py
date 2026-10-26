import json
import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class DatabaseSettingsTests(SimpleTestCase):
    def test_missing_empty_and_postgres_database_urls(self):
        # Load settings in fresh processes, just as manage.py does in CI.
        cases = [
            (None, "django.db.backends.sqlite3", "demo.sqlite3"),
            ("", "django.db.backends.sqlite3", "demo.sqlite3"),
            (
                "postgresql://example@localhost/settings_test",
                "django.db.backends.postgresql",
                "settings_test",
            ),
        ]
        script = (
            "import json; from config.settings import DATABASES; "
            "db = DATABASES['default']; "
            "print(json.dumps([db['ENGINE'], str(db['NAME'])]))"
        )
        for url, engine, name in cases:
            with self.subTest(database_url_state="unset" if url is None else "set"):
                env = os.environ.copy()
                env["DEMO"] = "1"
                if url is None:
                    env.pop("DATABASE_URL", None)
                else:
                    env["DATABASE_URL"] = url
                result = subprocess.run(
                    [sys.executable, "-c", script],
                    cwd=settings.BASE_DIR,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=15,
                )
                actual_engine, actual_name = json.loads(result.stdout)
                self.assertEqual(actual_engine, engine)
                self.assertEqual(actual_name.rsplit("/", 1)[-1], name)
