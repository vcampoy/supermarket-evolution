# Operación local

Los scripts están pensados para Windows PowerShell y no instalan servicios ni
dependencias externas. Ejecutalos desde el repositorio o usa rutas absolutas.

## Primera puesta en marcha

Sigue primero la [puesta en marcha de la raíz](../../README.md), que crea el
entorno estándar `src/backend/.venv` con Python 3.13, instala las dependencias y
el frontend, y aplica las migraciones.

La migración obligatoria se ejecuta así:

```powershell
Push-Location src/backend
try { ./.venv/Scripts/python.exe -m alembic upgrade head }
finally { Pop-Location }
```

El arranque no migra automáticamente: así se evita cambiar el esquema sin una
acción operativa explícita. Los scripts aceptan `-PythonExecutable` cuando sea
necesario, pero rechazan cualquier intérprete que no sea Python 3.13.x.

1. Instala las dependencias Python y Node según el README raíz.
2. Si vas a importar datos reales, completa `src/backend/.env` a partir de
   `.env.example`. El token local y las
   credenciales OAuth deben estar fuera del repositorio.
3. Autoriza Gmail sólo cuando quieras importar según
   [`docs/gmail-setup.md`](../../docs/gmail-setup.md).
4. Ejecuta `./src/scripts/start-local.ps1`. Compila la SPA y sirve `dist/` desde
   el backend en `http://127.0.0.1:8000`.

Para desarrollo con Vite, usa `npm run dev` en `src/frontend` y deja
`SUPERMARKET_CORS_ORIGINS` apuntando a `http://localhost:5173`.

## Sincronización programada

```powershell
./src/scripts/sync-tickets.ps1
./src/scripts/install-scheduled-task.ps1 -WhatIf
./src/scripts/install-scheduled-task.ps1
```

La tarea diaria se registra a las 03:00, comienza cuando Windows recupera una
ejecución omitida y no permite instancias simultáneas. El script tiene tres
reintentos como máximo por ejecución, y Windows añade hasta tres reinicios de
la tarea. Los logs rotan en `logs/sync-tickets.log` y no guardan la salida de
Gmail ni tokens.

## Tailscale y móvil

Tailscale se instala y autentica manualmente. Autoriza sólo tus dispositivos,
configura ACLs de la tailnet y, si queres un nombre HTTPS privado, usa
`tailscale serve` sobre el puerto local. No abras puertos del router, no uses
UPnP y no expongas el proceso a Internet.

```powershell
$env:SUPERMARKET_LOCAL_APP_TOKEN = '<token largo generado localmente>'
./src/scripts/start-backend.ps1 -BindAddress 100.101.102.103 -Port 8000
```

El script rechaza cualquier dirección que no sea loopback o una IP Tailscale
de `100.64.0.0/10`. Para HTTPS Serve, apunta Tailscale al backend local y
permite en la ACL sólo los dispositivos propios. El token anterior protege el
endpoint de sincronización manual; no es el refresh token de Gmail.

El PC debe permanecer encendido para consultar desde el móvil y para ejecutar
la sincronización. Si está apagado, Task Scheduler recupera la ejecución al
volver a iniciar Windows.

## Backups y restauración

```powershell
./src/scripts/backup-supermarket.ps1
./src/scripts/restore-supermarket.ps1 -ArchivePath .\backups\supermarket-evolution-<timestamp>.zip
```

El backup usa la API online de SQLite para incluir WAL de forma coherente,
conserva los PDF y sólo copia configuración no secreta (`alembic.ini` y
`.env.example`). Guarda los ZIP en un disco protegido y cifralos con una
herramienta del sistema si el medio no es confiable. Nunca incluyas `.env`,
tokens OAuth ni `secrets/`.

Para probar un restore sin tocar la instalación activa, usa un directorio
temporal como destino de `-DatabasePath`, `-TicketsDirectory` y
`-ConfigDirectory`, comprueba que SQLite responde a `PRAGMA integrity_check` y
que los SHA-256 de los PDF coinciden. Detene el backend antes de restaurar.

## Inspección y desinstalación

Todos los scripts que modifican estado aceptan `-WhatIf`. Para quitar la tarea:

```powershell
Unregister-ScheduledTask -TaskName 'Supermarket Evolution - Nightly Sync' -Confirm:$false
```

Esto no desinstala Tailscale ni borra datos, backups, PDFs o credenciales.
