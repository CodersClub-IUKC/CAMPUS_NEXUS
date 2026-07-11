import importlib
from types import SimpleNamespace
from unittest import TestCase


migration = importlib.import_module("campus_nexus.migrations.0049_django_admin_log_utf8mb4")


class DummyOps:
    def __init__(self):
        self.quoted = []

    def quote_name(self, identifier):
        self.quoted.append(identifier)
        return f"`{identifier}`"


class DummyCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql):
        self.connection.executed.append(sql)

    def fetchall(self):
        return self.connection.table_rows


class DummyConnection:
    def __init__(self, *, vendor="mysql", table_rows=()):
        self.vendor = vendor
        self.table_rows = table_rows
        self.executed = []
        self.ops = DummyOps()

    def cursor(self):
        return DummyCursor(self)


class DjangoAdminLogCharsetMigrationTests(TestCase):
    def test_unsupported_database_vendor_noops(self):
        connection = DummyConnection(
            vendor="sqlite",
            table_rows=[("django_admin_log",)],
        )
        schema_editor = SimpleNamespace(connection=connection)

        migration.harden_django_admin_log_charset(None, schema_editor)

        self.assertEqual(connection.executed, [])

    def test_missing_django_admin_log_table_noops(self):
        connection = DummyConnection(table_rows=[])
        schema_editor = SimpleNamespace(connection=connection)

        migration.harden_django_admin_log_charset(None, schema_editor)

        self.assertEqual(
            connection.executed,
            [
                """
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_TYPE = 'BASE TABLE'
              AND TABLE_NAME = 'django_admin_log'
            """
            ],
        )

    def test_only_django_admin_log_is_targeted(self):
        connection = DummyConnection(
            table_rows=[
                ("django_admin_log",),
                ("django_migrations",),
                ("django_session",),
                ("django_content_type",),
                ("auth_user",),
                ("token_blacklist_outstandingtoken",),
            ],
        )
        schema_editor = SimpleNamespace(connection=connection)

        migration.harden_django_admin_log_charset(None, schema_editor)

        alter_table_sql = [sql for sql in connection.executed if sql.startswith("ALTER TABLE")]
        self.assertEqual(
            alter_table_sql,
            [
                "ALTER TABLE `django_admin_log` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            ],
        )

    def test_table_identifier_is_quoted_through_connection_ops(self):
        connection = DummyConnection()

        sql = migration.convert_admin_log_charset_sql(connection)

        self.assertIn("ALTER TABLE `django_admin_log`", sql)
        self.assertEqual(connection.ops.quoted, ["django_admin_log"])

    def test_conversion_sql_uses_utf8mb4_unicode_ci(self):
        connection = DummyConnection()

        sql = migration.convert_admin_log_charset_sql(connection)

        self.assertIn("CONVERT TO CHARACTER SET utf8mb4", sql)
        self.assertIn("COLLATE utf8mb4_unicode_ci", sql)

    def test_no_broad_django_table_conversion_or_foreign_key_disable_is_implemented(self):
        migration_source = migration.__loader__.get_source(migration.__name__)

        self.assertNotIn("LIKE 'django", migration_source)
        self.assertNotIn("FOREIGN_KEY_CHECKS", migration_source)
