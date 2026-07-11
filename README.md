# Marketing Analytics Platform

A small marketing analytics platform: CSV upload as a data connector, pandas-based
cleaning and aggregation, a metrics dashboard, and an AI agent (Anthropic API)
that answers natural-language questions about the uploaded data — grounded in
the same aggregation functions the dashboard uses, via tool use.

Built as a portfolio project to demonstrate Django + DRF backend patterns for a
marketing analytics context: a real data-connector shape (CSV in, cleaned rows
out), a services layer separating business logic from HTTP, and an LLM feature
built as an agent with tools rather than a single stuffed prompt.

## Stack

- Django + Django REST Framework
- PostgreSQL
- pandas (CSV cleaning + aggregation)
- Anthropic API — manual tool-use loop (`claude-opus-4-8` by default)
- Docker / docker-compose for local dev
- pytest + pytest-django (35 tests)

## Architecture

```
CSV file
   │  POST /api/upload/
   ▼
analytics/services/ingestion.py   pandas: normalize columns, coerce types,
   │                              drop empty/invalid/duplicate rows
   ▼
CampaignRecord (Postgres)
   │
   ├──────────────────────────────┐
   ▼                              ▼
analytics/services/metrics.py    analytics/services/ai_agent.py
(get_summary/get_trends/         (Claude tool-use loop calling the
 get_top_campaigns - ORM          SAME three functions as tools)
 query → pandas aggregation)
   │                              │
   ▼                              ▼
DRF views (analytics/views.py) - thin: validate input, call one
service function, serialize the result. No pandas/business logic here.
   │
   ▼
Dashboard (vanilla JS + Chart.js) - fetch()es the API above
```

**Why a services layer.** Views only validate input (via DRF serializers) and
call a plain Python function; all the actual logic — CSV cleaning, aggregation,
the agent's tool-use loop — lives in `analytics/services/`. The payoff: the
dashboard's KPI tiles and the AI agent's answers both come from
`metrics.get_summary()` / `get_trends()` / `get_top_campaigns()` — there is no
separate "agent math," so the two surfaces can never disagree on a number.

**Why one Django app.** `analytics` holds everything. Splitting into multiple
apps at this scale would be premature structure for a project this size, and
would cost readability for no real benefit — an interviewer can see the whole
system in one directory.

## Project layout

```
config/                    Django project: settings (env-driven), urls, wsgi/asgi
analytics/
  models.py                 DataSource, CampaignRecord
  serializers.py             DRF request/response validation
  views.py                   Thin DRF views - validate, call a service, respond
  urls.py                     /api/* routes
  admin.py                    Django admin registration
  services/
    ingestion.py               pandas CSV cleaning + bulk_create (Step 3)
    metrics.py                  ORM → pandas aggregation (Step 4)
    ai_agent.py                  Anthropic tool-use loop (Step 6)
  static/analytics/           dashboard.css, dashboard.js
  templates/analytics/         dashboard.html
  tests/                        35 tests across 4 files + shared conftest.py
sample_data/campaign_performance.csv   generated sample data with messy rows
Dockerfile, docker-compose.yml, entrypoint.sh
```

## Setup

### Docker (recommended)

```bash
cp .env.example .env      # defaults work as-is; add ANTHROPIC_API_KEY to use the AI agent
docker compose up --build
```

Visit `http://localhost:8000/`. Postgres data persists in a named volume
across restarts; `docker compose down -v` to reset it.

### Local, without Docker

Requires a local Postgres (or edit `.env`'s `DATABASE_URL` to point at one).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

### Running the tests

```bash
pytest
```

All 35 tests use `@pytest.mark.django_db` where they touch the database, so
they run against whatever `DATABASE_URL` is configured (Postgres via Docker,
or a local Postgres). The AI agent tests mock `anthropic.Anthropic` entirely —
no API key or network access needed to run the suite.

## API reference

Base URL: `http://localhost:8000/api/`

| Method | Path | Description |
|---|---|---|
| `POST` | `/upload/` | Upload a CSV, ingest it |
| `GET` | `/datasources/` | Upload history (paginated) |
| `GET` | `/metrics/summary/` | Totals + CTR/CPC/CPA/ROAS |
| `GET` | `/metrics/trends/` | Time series of one metric |
| `GET` | `/metrics/top-campaigns/` | Top N campaigns by one metric |
| `POST` | `/ask/` | Ask a question in natural language |

### Upload a CSV

```bash
curl -X POST http://localhost:8000/api/upload/ \
  -F "file=@sample_data/campaign_performance.csv;type=text/csv"
```

```json
{"id":1,"file_name":"campaign_performance.csv","uploaded_at":"...","row_count":84,"status":"processed","error_message":""}
```

A schema mismatch or unparseable file returns the same shape with
`"status": "failed"` and `error_message` set, at HTTP 400.

### Metrics summary (optionally filtered)

```bash
curl "http://localhost:8000/api/metrics/summary/?channel=Google%20Ads&date_from=2026-01-01&date_to=2026-02-01"
```

```json
{"date_from":"2026-01-01","date_to":"2026-02-01","channel":"Google Ads","row_count":22,
 "totals":{"impressions":3000,"clicks":270,"cost":135.0,"conversions":26,"revenue":1290.0},
 "averages":{"ctr":0.09,"cpc":0.5,"cpa":5.1923,"roas":9.5556}}
```

### Trends

```bash
curl "http://localhost:8000/api/metrics/trends/?metric=revenue&granularity=week"
```

### Top campaigns

```bash
curl "http://localhost:8000/api/metrics/top-campaigns/?metric=revenue&limit=5"
```

### Ask a question

```bash
curl -X POST http://localhost:8000/api/ask/ \
  -H "Content-Type: application/json" \
  -d '{"question": "Which channel had the best ROAS?"}'
```

```json
{"answer": "Google Ads had the best ROAS at 9.6x over the uploaded date range.",
 "tool_calls": [{"tool": "get_summary", "input": {"channel": "Google Ads"}}]}
```

*(Illustrative — this project was built and verified without a real
`ANTHROPIC_API_KEY` in the environment, so the tool-use loop is covered by 8
mocked unit tests in `test_ai_agent.py`, not a live API call. The response
shape above is exactly what `answer_question()` returns; the specific wording
would come from Claude.)*

Returns `502` with a `detail` message if `ANTHROPIC_API_KEY` isn't configured
or the Anthropic API errors — the dashboard's ask-box surfaces this instead of
crashing.

## Design decisions

- **CSV cleaning is a pure pandas function, separate from the DB write.**
  `clean_campaign_data(df)` takes a DataFrame and returns a cleaned DataFrame
  plus drop-reason counts — no Django/DB import touched at runtime. `ingest_csv()`
  wraps it with the `bulk_create` and `DataSource` status update. This made the
  cleaning logic exhaustively unit-testable without a database, which mattered
  in practice: this project was built in an environment where Docker/Postgres
  wasn't always available, so the pure-function split let the core logic be
  verified immediately rather than blocked on infrastructure.
- **The AI agent is a manual tool-use loop, not a single prompt with a data
  dump.** Three tools map 1:1 to `metrics.get_summary`/`get_trends`/
  `get_top_campaigns`. Claude decides which to call and with what filters,
  based on the question — it can't invent numbers because it has to ask for
  them, and it's answering from the exact same aggregation code the dashboard
  renders from. Built as a plain manual loop (`while stop_reason == "tool_use"`)
  rather than the SDK's beta tool runner, to keep the request/response cycle
  fully visible and avoid a beta dependency.
- **No authentication system.** This is a single-tenant local demo with no
  login flow, so DRF's `DEFAULT_AUTHENTICATION_CLASSES` is set to `[]` with
  `AllowAny` permissions — leaving DRF's default `SessionAuthentication` on
  would enforce CSRF against the dashboard's own `fetch()` calls for no actual
  security benefit, since there's no session to protect.
- **One Django app, not several.** `analytics` holds models, services, views,
  and tests together. At this scale, splitting into `ingestion`/`metrics`/`ai`
  apps would add import indirection and settings boilerplate without adding
  real isolation - the `services/` package already gives each concern its own
  file.
- **Docker was used for verification throughout, not just written once at the
  end.** Steps 3-7 were verified against a throwaway local SQLite database
  (Docker Desktop wasn't always running) and then re-verified against the real
  Postgres container once Docker was available — running it for real in Step 8
  surfaced two actual bugs (an entrypoint permission issue caused by the dev
  bind mount, and a duplicate `STATICFILES_DIRS` entry) that reading the code
  wouldn't have caught.

## Known simplifications

- No auth/multi-tenancy - every upload is visible to everyone, appropriate for
  a local demo, not for a real deployment.
- No pagination on `/metrics/top-campaigns/` beyond `limit` - fine at demo data
  volumes, would need it for a large dataset.
- The dashboard's date-range filter is plain `<input type="date">` pairs
  rather than a full preset picker (today / last 7 / 30 / 90 days) - a
  reasonable scope cut for a single-page demo dashboard.
- The AI agent's tool-use loop is covered by 8 mocked unit tests, not a live
  call to the Anthropic API - this project was built without an
  `ANTHROPIC_API_KEY` in the environment. Everything downstream of "Claude
  responds with a tool_use or text block" is exercised for real (the loop
  logic, the tool dispatch into `metrics.py`, error handling); only the actual
  model call itself is mocked.
- No headless browser was available in this build environment, so the
  dashboard's JavaScript was verified by confirming every DOM element it
  references exists in the rendered HTML and by driving the underlying API
  endpoints directly - not by an actual screenshot of the rendered page.
