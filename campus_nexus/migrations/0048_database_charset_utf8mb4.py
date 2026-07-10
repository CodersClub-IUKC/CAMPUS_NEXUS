from django.db import migrations


TARGET_CHARACTER_SET = "utf8mb4"
TARGET_COLLATION = "utf8mb4_unicode_ci"
APP_TABLE_PREFIX = "campus_nexus_"


def is_mysql_compatible(connection):
    return connection.vendor == "mysql"


def is_campus_nexus_table(table_name):
    return isinstance(table_name, str) and table_name.startswith(APP_TABLE_PREFIX)


def quote_identifier(connection, identifier):
    return connection.ops.quote_name(identifier)


def alter_database_charset_sql(connection, database_name):
    return (
        f"ALTER DATABASE {quote_identifier(connection, database_name)} "
        f"CHARACTER SET {TARGET_CHARACTER_SET} COLLATE {TARGET_COLLATION}"
    )


def convert_table_charset_sql(connection, table_name):
    return (
        f"ALTER TABLE {quote_identifier(connection, table_name)} "
        f"CONVERT TO CHARACTER SET {TARGET_CHARACTER_SET} COLLATE {TARGET_COLLATION}"
    )


def campus_nexus_table_names_from_rows(rows):
    return sorted(
        table_name
        for row in rows
        for table_name in [row[0] if isinstance(row, (tuple, list)) else row]
        if is_campus_nexus_table(table_name)
    )


def get_active_database_name(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE()")
        row = cursor.fetchone()
    return row[0] if row else None


def get_campus_nexus_table_names(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_TYPE = 'BASE TABLE'
              AND TABLE_NAME LIKE 'campus_nexus\\_%'
            ORDER BY TABLE_NAME
            """
        )
        rows = cursor.fetchall()
    return campus_nexus_table_names_from_rows(rows)


def harden_database_charset(apps, schema_editor):
    connection = schema_editor.connection
    if not is_mysql_compatible(connection):
        return

    database_name = get_active_database_name(connection)
    if not database_name:
        return

    with connection.cursor() as cursor:
        cursor.execute(alter_database_charset_sql(connection, database_name))

    for table_name in get_campus_nexus_table_names(connection):
        with connection.cursor() as cursor:
            cursor.execute(convert_table_charset_sql(connection, table_name))


class Migration(migrations.Migration):

    dependencies = [
        ("campus_nexus", "0047_feedback_admin_response_feedback_category_and_more"),
    ]

    operations = [
        migrations.RunPython(harden_database_charset, reverse_code=migrations.RunPython.noop),
    ]
