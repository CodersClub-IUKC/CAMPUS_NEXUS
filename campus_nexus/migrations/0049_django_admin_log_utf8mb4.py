from django.db import migrations


TARGET_CHARACTER_SET = "utf8mb4"
TARGET_COLLATION = "utf8mb4_unicode_ci"
ADMIN_LOG_TABLE = "django_admin_log"


def is_mysql_compatible(connection):
    return connection.vendor == "mysql"


def quote_identifier(connection, identifier):
    return connection.ops.quote_name(identifier)


def admin_log_table_exists_from_rows(rows):
    return any(
        (row[0] if isinstance(row, (tuple, list)) else row) == ADMIN_LOG_TABLE
        for row in rows
    )


def convert_admin_log_charset_sql(connection):
    return (
        f"ALTER TABLE {quote_identifier(connection, ADMIN_LOG_TABLE)} "
        f"CONVERT TO CHARACTER SET {TARGET_CHARACTER_SET} COLLATE {TARGET_COLLATION}"
    )


def django_admin_log_exists(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_TYPE = 'BASE TABLE'
              AND TABLE_NAME = 'django_admin_log'
            """
        )
        rows = cursor.fetchall()
    return admin_log_table_exists_from_rows(rows)


def harden_django_admin_log_charset(apps, schema_editor):
    connection = schema_editor.connection
    if not is_mysql_compatible(connection):
        return

    if not django_admin_log_exists(connection):
        return

    with connection.cursor() as cursor:
        cursor.execute(convert_admin_log_charset_sql(connection))


class Migration(migrations.Migration):

    dependencies = [
        ("campus_nexus", "0048_database_charset_utf8mb4"),
    ]

    operations = [
        migrations.RunPython(harden_django_admin_log_charset, reverse_code=migrations.RunPython.noop),
    ]
