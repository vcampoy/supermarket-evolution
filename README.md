# Supermarket Evolution

Aplicación local-first para consultar tickets y evolución de precios. El bootstrap de Prompt 02 deja preparado un backend FastAPI con SQLite/Alembic y un shell React accesible; la importación Gmail se implementará en una fase posterior.

## Desarrollo reproducible

### Backend

```powershell
cd src/backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.api.main:app --reload
```

### Frontend

```powershell
cd src/frontend
npm ci
npm run dev
```

Verificaciones: `ruff check .`, `mypy app`, `pytest`, `npm run lint`, `npm run type-check`, `npm test` y `npm run build`.
