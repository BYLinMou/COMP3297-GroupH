import os
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from betatrax.settings import _database_config_from_env, _database_config_from_url


class DatabaseUrlConfigTests(SimpleTestCase):
    def test_postgresql_database_url_builds_django_config(self):
        engine, config = _database_config_from_url(
            "postgresql://db_user:p%40ss@db.local:15432/betatrax?sslmode=require"
        )

        self.assertEqual(engine, "postgresql")
        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "betatrax")
        self.assertEqual(config["USER"], "db_user")
        self.assertEqual(config["PASSWORD"], "p@ss")
        self.assertEqual(config["HOST"], "db.local")
        self.assertEqual(config["PORT"], "15432")
        self.assertEqual(config["OPTIONS"], {"sslmode": "require"})

    def test_sqlite_database_url_builds_django_config(self):
        engine, config = _database_config_from_url("sqlite:///./data/db.sqlite3")
        self.assertEqual(engine, "sqlite")
        self.assertEqual(config["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(config["NAME"], "./data/db.sqlite3")

        self.assertEqual(_database_config_from_url("sqlite:///db.sqlite3")[1]["NAME"], "db.sqlite3")
        self.assertEqual(_database_config_from_url("sqlite:////data/db.sqlite3")[1]["NAME"], "/data/db.sqlite3")
        self.assertEqual(_database_config_from_url("sqlite:///:memory:")[1]["NAME"], ":memory:")

    def test_database_url_validation_errors_are_explicit(self):
        invalid_cases = [
            ("mysql://user:pass@localhost/betatrax", "DATABASE_URL must use"),
            ("postgresql://localhost", "database name"),
            ("postgresql://localhost:bad/betatrax", "invalid port"),
            ("sqlite://localhost/db.sqlite3", "must not include a host"),
            ("sqlite://", "must include a database path"),
        ]

        for url, message in invalid_cases:
            with self.subTest(url=url):
                with self.assertRaisesMessage(ImproperlyConfigured, message):
                    _database_config_from_url(url)

    @patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgres://url_user:url_pass@db.example.com:5433/url_db",
            "DATABASE_ENGINE": "sqlite",
            "SQLITE_PATH": "./legacy.sqlite3",
        },
        clear=True,
    )
    def test_database_url_takes_precedence_over_legacy_variables(self):
        engine, config = _database_config_from_env()

        self.assertEqual(engine, "postgresql")
        self.assertEqual(config["NAME"], "url_db")
        self.assertEqual(config["USER"], "url_user")
        self.assertEqual(config["HOST"], "db.example.com")

    @patch.dict(
        os.environ,
        {
            "DATABASE_ENGINE": "postgresql",
            "POSTGRES_DB": "legacy_db",
            "POSTGRES_USER": "legacy_user",
            "POSTGRES_PASSWORD": "legacy_pass",
            "POSTGRES_HOST": "legacy-host",
            "POSTGRES_PORT": "5434",
        },
        clear=True,
    )
    def test_legacy_postgres_variables_still_work_without_database_url(self):
        engine, config = _database_config_from_env()

        self.assertEqual(engine, "postgresql")
        self.assertEqual(config["NAME"], "legacy_db")
        self.assertEqual(config["USER"], "legacy_user")
        self.assertEqual(config["PASSWORD"], "legacy_pass")
        self.assertEqual(config["HOST"], "legacy-host")
        self.assertEqual(config["PORT"], "5434")
