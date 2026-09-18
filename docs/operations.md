# Operación, seguridad y recuperación

## Arranque local

El modo soportado es `src/scripts/start-local.ps1`. Construye la aplicación
React y la sirve como estático desde FastAPI. El bind predeterminado es
`127.0.0.1:8000`; no cambia el diseño visual ni crea una exposición de red.

```powershell
./src/scripts/start-local.ps1
```

Para comprobar sólo las acciones sin ejecutar cambios:

```powershell
./src/scripts/start-local.ps1 -WhatIf
./src/scripts/install-scheduled-task.ps1 -WhatIf
./src/scripts/sync-tickets.ps1 -WhatIf
```

## Sincronización nocturna

`install-scheduled-task.ps1` registra o actualiza de forma idempotente la tarea
`Supermarket Evolution - Nightly Sync` a las 03:00. `StartWhenAvailable` hace
que Windows ejecute la tarea cuando vuelve a estar disponible después de una
ejecución perdida. `MultipleInstances IgnoreNew` y un mutex con nombre en
`sync-tickets.ps1` cubren tanto el solapamiento de Task Scheduler como dos
invocaciones manuales.

Cada ejecución llama a `python -m app.cli sync --since-last`, reintenta como
máximo tres veces y deja sólo estado operativo (inicio, resultado y código de
salida) en `logs/sync-tickets.log`. El log rota al superar 5 MiB y conserva
cinco copias. No se escribe la respuesta de Gmail, el contenido de PDFs, el
refresh token ni el token local.

## Acceso móvil con Tailscale

Tailscale debe instalarse, iniciar sesión y autorizarse manualmente. Configura
ACLs para tus dispositivos y usa `tailscale serve` si queres un hostname HTTPS
privado. El proyecto no invoca la autenticación de Tailscale, no abre puertos
del router y no usa UPnP.

El proceso sólo admite loopback o una IP Tailscale explícita del rango
`100.64.0.0/10`:

```powershell
$env:SUPERMARKET_LOCAL_APP_TOKEN = '<secreto local fuera de Git>'
./src/scripts/start-backend.ps1 -BindAddress 100.101.102.103
```

El token local es distinto de OAuth. Protege la sincronización manual remota;
el dispositivo también debe estar autorizado por la ACL de la tailnet. Nunca
uses `0.0.0.0`, port-forwarding ni un proxy público. El ordenador debe estar
encendido para que el móvil consulte datos o para que se ejecute la tarea.

## OAuth y configuración

Guarda `gmail-client-secret.json`, `gmail-token.json`, `.env` y el token local
fuera del repositorio. El alcance Gmail es sólo `gmail.readonly`. Revisa
[`docs/gmail-setup.md`](gmail-setup.md) antes de ejecutar `gmail-auth`.

## Backup coherente

```powershell
./src/scripts/backup-supermarket.ps1
```

El backup usa la API online de SQLite, por lo que el snapshot incluye el estado
coherente de la base aunque SQLite esté en WAL. El ZIP contiene:

- `database.sqlite3` validada con `PRAGMA integrity_check`;
- los PDF de `tickets/`, excluyendo temporales `.partial-*`;
- `alembic.ini` y `.env.example` como configuración no secreta;
- `manifest.json` con SHA-256.

Protege el directorio de backups y cifra los ZIP cuando salgan del equipo.
El script no puede cifrar por sí mismo sin imponer una herramienta del sistema.

## Restore probado

Detén el backend y restaura sobre directorios temporales antes de tocar la
instalación real:

```powershell
./src/scripts/restore-supermarket.ps1 `
  -ArchivePath .\backups\supermarket-evolution-<timestamp>.zip `
  -DatabasePath $env:TEMP\supermarket-restore\supermarket-evolution.db `
  -TicketsDirectory $env:TEMP\supermarket-restore\tickets `
  -ConfigDirectory $env:TEMP\supermarket-restore\config
```

La restauración verifica el manifest y cada hash antes de copiar. Valida luego
`PRAGMA integrity_check` y compara los SHA-256 de los PDF con el backup. Los
archivos existentes con el mismo nombre se reemplazan; los archivos extra no
se borran automáticamente para evitar una pérdida accidental.

## Desinstalación

```powershell
Unregister-ScheduledTask -TaskName 'Supermarket Evolution - Nightly Sync' -Confirm:$false
```

Esto sólo elimina la tarea; no desinstala Tailscale ni elimina PDFs, bases,
backups o credenciales.
