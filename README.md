# Marketing Analytics Platform

A small marketing analytics platform built with Django + Django REST Framework:
CSV upload as a data connector, pandas-based cleaning/aggregation, a metrics
dashboard, and an AI agent (Anthropic API) that answers natural-language
questions about the uploaded data.

Status: work in progress — built incrementally, see commit history.

## Stack

- Django + Django REST Framework
- PostgreSQL
- pandas (CSV cleaning + aggregation)
- Anthropic API (tool-use agent)
- Docker / docker-compose for local dev

## Local setup (without Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in DATABASE_URL / ANTHROPIC_API_KEY
python manage.py migrate
python manage.py runserver
```

## Local setup (Docker)

```bash
docker compose up --build
```

More setup and architecture notes are added as the project is built out.
