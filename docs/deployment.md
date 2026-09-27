# Deployment

## Local, without Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
python -m ciri bootstrap
python -m uvicorn api.main:app --app-dir . --port 8766
python -m streamlit run streamlit_app/app.py --server.port 8765 --server.address 0.0.0.0
```

The warehouse file is `data/warehouse/ciri.db`. Leave `DATABASE_URL` unset.

## Docker Compose with PostgreSQL

Docker is not required for the local console. Use it when you want the star schema in Postgres, which is also what Power BI should connect to.

```bash
docker compose up --build
```

- Console: port 8765
- API: port 8766
- Postgres: port 54329, database `ciri`, user `ciri`, password `ciri`

The entrypoint runs `python -m ciri bootstrap` before the process starts, so the first boot loads and trains against Postgres. Change the password before any shared environment. Copy `.env.example` to `.env` for the analyst key.

## Analyst model

```bash
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://api.openai.com/v1   # or any compatible host
export OPENAI_MODEL=gpt-4o-mini
```

With no key, the assistant still answers from the warehouse.

## CI

GitHub Actions installs `requirements.txt` and runs `pytest`. The weekly refresh workflow runs `python -m ciri bootstrap --tiny` and uploads the registry and metrics as artifacts. Point that workflow at a real warehouse and drop `--tiny` when you want a full retrain on a schedule.

## Tests

```bash
PYTHONPATH=src pytest
```

The platform test builds a short grid in a temporary database. It does not touch `data/warehouse/ciri.db`.
