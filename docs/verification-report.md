# Informe de verificación final

**Decisión: `NOT READY`**

La revisión independiente confirma que el código y los fixtures anonimizados
superan las verificaciones automatizadas disponibles. La entrega no puede
declararse lista porque todavía faltan el consentimiento OAuth explícito, el
backfill real, una prueba manual de móvil y la instalación/verificación de la
tarea nocturna en el equipo objetivo.

## Alcance y reglas de seguridad

- Se revisó exclusivamente el alcance del Prompt 07 sobre `origin/main` en
  `e188456`.
- No se accedió a Gmail real, no se ejecutó backfill real y no se solicitaron ni
  manipularon contraseñas, 2FA, refresh tokens o secretos OAuth.
- La importación ejecutada usa únicamente
  `src/backend/tests/fixtures/normal_ticket.pdf`, que contiene datos sintéticos.

## Matriz de criterios

| Criterio | Evidencia | Resultado |
|---|---|---|
| Importación de fixture e idempotencia | `TicketSyncService` procesó dos mensajes con el mismo SHA-256: primera ejecución `imported_tickets=1`, `skipped_duplicates=1`; segunda `skipped_duplicates=2`; conteos finales `gmail_messages=2`, `tickets=1`, `ticket_items=3`, PDFs=1. | PASS |
| Parser unidad, varias unidades y peso | `tests/test_parser.py`, fixture PDF real anonimizada y `tests/test_pricing.py`; se verificaron cantidad, 740 g, 219 céntimos/kg y redondeo `ROUND_HALF_UP`. | PASS |
| Tickets, orden y paginación de 50 | `tests/test_api.py::test_ticket_pagination_is_stable_and_bounded`; 50 elementos en página 1 y 1 en página 2, con orden estable. | PASS |
| Detalle, totales y navegación | `tests/test_api.py` y `src/frontend/src/App.test.tsx`; total antes/después, navegación ticket-producto-ticket y estado 404 seguro. | PASS |
| Búsqueda, gráfica y tabla equivalente | `src/frontend/src/App.test.tsx`; búsqueda por teclado, selección, historia y tabla accesible cubierta con MSW. | PASS |
| Estados de interfaz | Tests de carga, error/404, vacío, reintento, parcial y ejecución de sincronización. | PASS en tests |
| Responsive móvil/escritorio | Smoke visual local con estado seguro de backend no disponible en 1280x800 y 390x844; el menú móvil abre y muestra cierre accesible. No sustituye la prueba con datos reales. | PASS parcial |
| Accesibilidad | Árbol accesible del navegador confirmó menú expandible, navegación y botón de reintento; también hay foco visible, teclado y tabla alternativa cubiertos en código/tests. No se ejecutó auditoría automatizada completa. | PASS parcial |
| Backend | `28 passed`; Ruff y mypy sin errores. | PASS |
| Frontend | lint, type-check, 7 tests y build Vite sin errores. | PASS |
| Migración limpia | Base SQLite temporal creada desde cero con `alembic upgrade head`; versión `0002`, tablas de dominio presentes. | PASS |
| Precisión decimal y zonas horarias | Decimal/céntimos en dominio y API; test de redondeo; próximo scheduler y formato UI fijados a `Europe/Madrid`. | PASS |
| Deduplicación y transacciones | Deduplicación por `provider_message_id` y SHA-256; rollback por mensaje; prueba de importación repetida. | PASS en alcance de fixture |
| N+1 en listados | El listado de tickets usa consulta de conteo + consulta paginada y quedó cubierto con contador `<=2`. | PASS para listado |
| Secretos y datos reales versionados | Búsqueda de tokens/secretos; `git ls-files` sólo contiene el PDF fixture anonimizado y `.env.example`; bases, entornos, tokens y `tickets/` están ignorados. | PASS |
| Rutas absolutas | Las rutas de runtime son configurables/defaults; las absolutas restantes están en documentación, tests o URLs locales. | PASS |
| Tarea nocturna | Scripts idempotentes y tests PowerShell de reintentos/no solapamiento; la tarea no está instalada ni probada en el equipo objetivo. | PENDIENTE |
| Gmail real y backfill | Requieren consentimiento explícito del usuario, que no está disponible en esta revisión. | BLOQUEADO |

## Comandos y resultados

Ejecutados desde `src/backend` salvo indicación contraria:

```text
.venv313\Scripts\python.exe -m pytest -q
28 passed in 5.46s

.venv313\Scripts\python.exe -m ruff check app tests
All checks passed!

.venv313\Scripts\python.exe -m mypy app
Success: no issues found in 25 source files

npm run lint
OK
npm run type-check
OK
npm test -- --run
7 tests passed
npm run build
OK; warning informativo de bundle >500 kB

alembic upgrade head sobre SQLite temporal
OK; version=0002_ingestion_metadata

scripts PowerShell start-local/start-backend/sync-tickets/install-scheduled-task -WhatIf
OK; no se crearon logs ni se iniciaron procesos
```

La primera invocación global de `python -m pytest` usó el Python 3.12 del
`PATH`, que no tenía pytest. Se repitió con el entorno Python 3.13 del proyecto
(`.venv313` en aquella revisión), coherente con `pyproject.toml`. La puesta en
marcha actual estandariza el entorno como `.venv` y valida que sea Python 3.13.

## Fallos encontrados y corregidos

1. **La API anunciaba siempre que no había próxima ejecución.** Se añadió el
   cálculo del siguiente `03:00` local en `Europe/Madrid` y un test de borde
   antes/después de esa hora.
2. **La interfaz formateaba fechas en la zona horaria del dispositivo.** Ahora
   fuerza `Europe/Madrid`, que es la zona contractual del ticket.
3. **Las tablas de historia podían producir claves React duplicadas** cuando un
   producto aparecía varias veces en el mismo ticket. Se usan claves compuestas
   con el índice de observación.
4. **La puesta en marcha no indicaba aplicar migraciones.** Se documentó el
   comando explícito `alembic upgrade head`; el arranque no migra
   automáticamente para evitar cambios de esquema implícitos.
5. **Los scripts podían elegir un entorno Python incompatible** aunque el
   proyecto exige Python 3.13. Ahora validan la versión antes de usar `.venv`,
   el entorno heredado `.venv313`, `python` o `-PythonExecutable`.

## Pasos manuales exactos pendientes

### OAuth y backfill real

1. Crear o seleccionar un proyecto en Google Cloud Console.
2. Habilitar Gmail API y configurar la pantalla de consentimiento.
3. Añadir la cuenta de uso como usuario de prueba cuando corresponda.
4. Crear credenciales OAuth de tipo **Desktop app**.
5. Guardar el JSON descargado fuera de Git y configurar
   `SUPERMARKET_GMAIL_CLIENT_SECRETS_PATH`.
6. Confirmar explícitamente antes de continuar con el consentimiento OAuth.
7. Desde `src/backend`, ejecutar
   `.\.venv\Scripts\python.exe -m app.cli gmail-auth` y completar el navegador
   local sin compartir secretos en el chat.
8. Verificar que la cuenta autorizada coincide con
   `SUPERMARKET_GMAIL_ACCOUNT`.
9. Ejecutar `.\.venv\Scripts\python.exe -m app.cli sync --all`.
10. Comparar sin mostrar contenido sensible el número de mensajes, PDFs,
    tickets y registros `needs_review`.
11. Ejecutar dos veces
    `.\.venv\Scripts\python.exe -m app.cli sync --since-last` y comprobar que
    no aumentan tickets duplicados ni PDFs duplicados.

### Tailscale y prueba móvil

1. Instalar Tailscale manualmente e iniciar sesión en el equipo y el móvil.
2. Restringir la ACL de la tailnet a los dispositivos propios.
3. Confirmar la IP Tailscale IPv4 del PC dentro de `100.64.0.0/10`.
4. Definir un token local nuevo fuera del repositorio en
   `SUPERMARKET_LOCAL_APP_TOKEN`.
5. Arrancar con `src/scripts/start-backend.ps1 -BindAddress <IP_TAILSCALE>`.
6. Si se desea HTTPS privado, configurar manualmente `tailscale serve` sin
   abrir puertos del router.
7. Desde el móvil autorizado, comprobar tickets, detalle, búsqueda, gráfica,
   sincronización, foco/teclado cuando aplique y lectura en viewport pequeño.

### Tarea nocturna

1. Confirmar que el backend está detenido o controlado antes de instalar la
   tarea.
2. Ejecutar `src/scripts/install-scheduled-task.ps1 -WhatIf`.
3. Revisar que muestra las 03:00 y `StartWhenAvailable`/`IgnoreNew`.
4. Ejecutar `src/scripts/install-scheduled-task.ps1`.
5. Verificar en Task Scheduler la tarea
   `Supermarket Evolution - Nightly Sync` y ejecutar una simulación controlada
   sin Gmail real.

## Riesgos residuales

- El parser no usa OCR; PDFs sin texto extraíble quedan para revisión.
- La cobertura de formatos reales de Mercadona no puede certificarse sin el
  consentimiento OAuth y un backfill controlado.
- El bundle frontend supera 500 kB minificado; el build termina correctamente,
  pero conviene dividirlo antes de una distribución más amplia.
- Los ZIP de backup deben cifrarse con una herramienta del sistema si salen del
  equipo; el proyecto no impone una herramienta de cifrado.
