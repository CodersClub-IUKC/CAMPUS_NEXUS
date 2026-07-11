# Database Charset Hardening

Production MariaDB originally inherited `latin1` defaults, while Django writes valid Unicode through both Campus Nexus audit logging and Django Admin logging. A production backup is required before running ALTER TABLE migrations.

## 0048 Application Tables

Migration `0048_database_charset_utf8mb4` changed the active database default to `utf8mb4` / `utf8mb4_unicode_ci` and converted application-owned `campus_nexus_%` base tables. This fixed Unicode writes to `campus_nexus_auditlog`, including object representations such as:

```text
Member Name → Association Name
```

## 0049 Django Admin Log

Django Admin also writes object representations to `django_admin_log` through `LogEntry`. Because that table is owned by Django, it was intentionally outside the `campus_nexus_%` scope of migration `0048` and could still inherit the original `latin1` schema.

After `0048`, valid Unicode membership object representations could still raise MariaDB `DataError 1366` when Django Admin inserted a `LogEntry.object_repr` containing `→`.

Migration `0049_django_admin_log_utf8mb4` narrowly converts only the `django_admin_log` base table to `utf8mb4` / `utf8mb4_unicode_ci`. It does not convert other Django, auth, session, migration, or token blacklist tables.
