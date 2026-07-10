import importlib
from unittest import TestCase
from types import SimpleNamespace


migration = importlib.import_module("campus_nexus.migrations.0048_database_charset_utf8mb4")


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

    def fetchone(self):
        return (self.connection.database_name,)

    def fetchall(self):
        return self.connection.table_rows


class DummyConnection:
    def __init__(self, *, vendor="mysql", database_name="campus_nexus", table_rows=()):
        self.vendor = vendor
        self.database_name = database_name
        self.table_rows = table_rows
        self.executed = []
        self.ops = DummyOps()

    def cursor(self):
        return DummyCursor(self)


class DatabaseCharsetMigrationTests(TestCase):
    def test_only_campus_nexus_tables_are_selected_for_conversion(self):
        rows = [
            ("campus_nexus_auditlog",),
            ("campus_nexus_membership",),
            ("auth_user",),
            ("django_migrations",),
            ("token_blacklist_outstandingtoken",),
        ]

        self.assertEqual(
            migration.campus_nexus_table_names_from_rows(rows),
            ["campus_nexus_auditlog", "campus_nexus_membership"],
        )

    def test_sql_identifiers_are_quoted_through_connection_ops(self):
        connection = DummyConnection()

        database_sql = migration.alter_database_charset_sql(connection, "campus_nexus")
        table_sql = migration.convert_table_charset_sql(connection, "campus_nexus_auditlog")

        self.assertIn("ALTER DATABASE `campus_nexus`", database_sql)
        self.assertIn("ALTER TABLE `campus_nexus_auditlog`", table_sql)
        self.assertEqual(connection.ops.quoted, ["campus_nexus", "campus_nexus_auditlog"])

    def test_unsupported_database_vendor_does_not_execute_mariadb_sql(self):
        connection = DummyConnection(
            vendor="sqlite",
            table_rows=[("campus_nexus_auditlog",)],
        )
        schema_editor = SimpleNamespace(connection=connection)

        migration.harden_database_charset(None, schema_editor)

        self.assertEqual(connection.executed, [])

    def test_forward_migration_converts_only_campus_nexus_tables(self):
        connection = DummyConnection(
            table_rows=[
                ("auth_user",),
                ("campus_nexus_auditlog",),
                ("django_migrations",),
                ("campus_nexus_membership",),
                ("token_blacklist_blacklistedtoken",),
            ],
        )
        schema_editor = SimpleNamespace(connection=connection)

        migration.harden_database_charset(None, schema_editor)

        alter_table_sql = [sql for sql in connection.executed if sql.startswith("ALTER TABLE")]
        self.assertEqual(
            alter_table_sql,
            [
                "ALTER TABLE `campus_nexus_auditlog` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
                "ALTER TABLE `campus_nexus_membership` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            ],
        )
