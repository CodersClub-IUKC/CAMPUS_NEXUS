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

