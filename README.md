# CAMPUS NEXUS

## How to run the project

1. Create virtual environment

```python
python -m venv .venv

source .venv/bin/activate

```
2. Install the python dependencies

```python
pip install -r requirements.txt
```

3. Install the sass compiler

```bash
npm install -g sass
```

This dependency is required for theme generation. **You need to have npm installed**

4. Make migrations

```python
python manage.py makemigrations
```

5. Apply migrations

```
python manage.py migrate
```

6. Run web server

```python
python manage.py runserver
```

## Import members from ERP CSV

Use this command to bulk import student/member data from the campus ERP export:

```bash
python manage.py import_members_csv /path/to/members.csv --dry-run
python manage.py import_members_csv /path/to/members.csv --create-missing-relations --created-by <staff_username>
```

Expected CSV headers (aliases are supported):

- `first_name`
- `last_name`
- `email`
- `phone`
- `registration_number`
- `national_id_number`
- `member_type` (`student`, `alumni`, `external`)
- `faculty`
- `course`
- `nationality`

Recommended process:

1. Export CSV from ERP.
2. Run `--dry-run` first and fix all skipped-row errors.
3. Run the committed import command.
4. Use admin for manual additions (guild admin or superuser only).
