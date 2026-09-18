# Supermarket Evolution

Aplicación local para consultar tickets y ver la evolución de precios. El flujo
soportado en Windows usa **Python 3.13**, SQLite/Alembic, FastAPI y una interfaz
React compilada y servida por el propio backend.

## Puesta en marcha rápida (Windows/PowerShell)

Requisitos: [uv](https://docs.astral.sh/uv/), Node.js con npm y PowerShell.
Ejecuta estos comandos desde la raíz del repositorio:

```powershell
# 1. Crear el entorno Python 3.13 e instalar backend + herramientas de desarrollo
cd src/backend
uv venv --clear --python 3.13 --seed .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 2. Crear o actualizar la base de datos local
.\.venv\Scripts\python.exe -m alembic upgrade head

# 3. Instalar el frontend
cd ..\frontend
npm ci

# 4. Volver a la raíz, compilar el frontend y arrancar la aplicación
cd ..\..
.\src\scripts\start-local.ps1
```

Abre <http://127.0.0.1:8000>. Para detener la aplicación, pulsa `Ctrl+C`.
El primer arranque muestra una base vacía: Gmail no es necesario para comprobar
la instalación.

## Comprobar que funciona

Con la aplicación arrancada:

- interfaz: <http://127.0.0.1:8000>;
- salud de la API: <http://127.0.0.1:8000/api/v1/health>;
- documentación de la API: <http://127.0.0.1:8000/docs>.

La migración es obligatoria antes del primer arranque. El backend no modifica el
esquema de la base automáticamente.

## Versión de Python

El backend admite **Python 3.13.x** (`>=3.13,<3.14`). Es la versión usada por
Ruff, mypy, los tests y los scripts operativos. Python 3.12 no está soportado y
Python 3.14 no se declara compatible porque todavía no se ha validado todo el
conjunto de dependencias con esa versión.

No uses el `python` global sin comprobarlo. En este equipo apunta a Python 3.12,
y el launcher puede listar un runtime Astral 3.13 aunque `py -3.13` no consiga
resolverlo. `uv venv --python 3.13` selecciona directamente un runtime 3.13 y
evita depender del `PATH` o de ese selector del launcher.

Comprueba siempre el entorno creado:

```powershell
cd src/backend
.\.venv\Scripts\python.exe --version
# Debe imprimir Python 3.13.x
```

Si `.venv` ya existe con otra versión, el comando `uv venv --clear ...` de la
puesta en marcha la recrea. Los scripts rechazan automáticamente Python 3.12 o
3.14 en lugar de fallar más tarde con dependencias incompatibles.

## Desarrollo

Para ejecutar backend y frontend por separado:

```powershell
# Terminal 1
cd src/backend
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload

# Terminal 2
cd src/frontend
npm run dev
```

Vite queda disponible en <http://localhost:5173> y usa la API local.

## Verificaciones

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m mypy app

cd ..\frontend
npm run lint
npm run type-check
npm test -- --run
npm run build
```

## Configuración y datos reales

La aplicación puede arrancar sin OAuth. Para importar tickets reales, copia
`src/backend/.env.example` como `.env` y sigue
[`docs/gmail-setup.md`](docs/gmail-setup.md). No guardes credenciales, tokens ni
la base local en Git.

La operación nocturna, Tailscale, backups y restauración se explican en
[`docs/operations.md`](docs/operations.md) y
[`src/scripts/README.md`](src/scripts/README.md).

## Problemas frecuentes

### `No runtime installed that matches 3.13`

No uses `py -3.13` en este equipo. Ejecuta desde `src/backend`:

```powershell
uv python find 3.13
uv venv --clear --python 3.13 --seed .venv
```

### PowerShell bloquea un script

Permite scripts locales para tu usuario y vuelve a abrir PowerShell:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### La API devuelve un error de base de datos

Aplica la migración desde `src/backend`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```
