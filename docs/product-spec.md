# Especificación de producto

Mercadona Evolution es una aplicación personal local-first para importar los tickets digitales de Mercadona desde Gmail, conservar sus PDF originales y consultar la evolución histórica de precios desde escritorio o móvil. El backend es la única fuente de verdad para reglas de parsing, normalización y precio comparable.

## Alcance y lenguaje del dominio

| Concepto | Definición verificable |
|---|---|
| Ticket | Compra identificada por un mensaje de Gmail y su PDF original. |
| Línea | Renglón de compra parseado; conserva la descripción original, cantidad/peso e importe. |
| Producto | Entidad canónica a la que una línea puede quedar vinculada de forma conservadora. |
| Precio comparable | Para unidades, céntimos por unidad; para peso, céntimos por kg. Nunca se mezclan ambas series. |
| Importe de línea | Importe total cobrado por la línea, en céntimos. |
| Fecha del ticket | Fecha/hora del ticket en `Europe/Madrid`; los eventos técnicos se almacenan en UTC. |

## Requisitos funcionales

### RF-01 — Listado de tickets

La aplicación DEBE mostrar un menú lateral izquierdo en escritorio y desplegable en móvil. `/tickets` DEBE mostrar una tabla ordenada por fecha descendente. Cada fila DEBE incluir fecha, cantidad de líneas y total. La página DEBE contener exactamente 50 tickets cuando existan al menos 50 resultados; la última página puede contener menos. La fila completa DEBE navegar a `/tickets/:ticketId`.

**Criterios de aceptación**

- `GET /api/v1/tickets?page=1&pageSize=50` devuelve como máximo 50 elementos, `totalItems` y `totalPages`.
- El orden por defecto es `purchasedAt DESC, id DESC` para que sea estable.
- La interfaz muestra estados de carga, vacío, error y datos parcialmente parseados.
- Un ticket parcialmente parseado sigue siendo visible y enlazable; el estado explica qué falta.

### RF-02 — Detalle de ticket

`/tickets/:ticketId` DEBE mostrar el total antes y después de la tabla de líneas. Cada línea DEBE mostrar descripción original, cantidad o peso, precio comparable con su base (`unit` o `kg`) e importe de línea. La acción de la línea DEBE abrir la evolución del producto cuando exista un producto vinculado; si no existe, debe explicar que la línea requiere revisión.

**Criterios de aceptación**

- Los céntimos se formatean como dinero sin convertirlos a `float`.
- Una línea por unidades muestra cantidad y `cents/unit`; una línea a peso muestra peso y `cents/kg`.
- La UI no calcula precios: consume `comparablePrice` y `comparableBasis` de la API.
- Las líneas no vinculadas no inventan un producto ni una serie histórica.

### RF-03 — Búsqueda y detalle de productos

`/products` DEBE ofrecer un buscador autocompletado y accesible. La selección navega a `/products/:productId`. El detalle DEBE mostrar gráfica temporal, resumen de cambio y tabla paginada de tickets donde aparece el producto; cada ticket DEBE enlazar a su detalle.

**Criterios de aceptación**

- El autocompletado funciona con teclado, nombre accesible y estado sin resultados.
- La gráfica sólo recibe observaciones de una misma base comparable.
- La tabla accesible contiene los mismos puntos que la gráfica.
- El resumen diferencia primera observación, última observación, variación absoluta y variación porcentual; si no hay dos observaciones, indica que no se puede calcular.

### RF-04 — Sincronización

El sistema DEBE soportar un backfill inicial de todos los mensajes que coincidan con `from:(ticket_digital@mail.mercadona.com) has:attachment filename:pdf`, una sincronización incremental nocturna a las 03:00 y una ejecución manual local. Las tres modalidades DEBEN ser idempotentes.

**Criterios de aceptación**

- El mismo `gmailMessageId` no crea un segundo ticket.
- El mismo PDF se identifica también por SHA-256 y se conserva sin sobrescribir un original distinto.
- La ejecución manual devuelve un identificador de ejecución y expone progreso, última ejecución y errores accionables.
- Al arrancar el PC se recuperan ejecuciones omitidas según la política documentada en arquitectura.
- El sistema informa que el PC debe estar encendido para sincronizar y para acceder remotamente.

### RF-05 — Conservación y trazabilidad

- Cada PDF original se guarda en `tickets/` y su ruta, tamaño y SHA-256 quedan registrados.
- Una línea conserva siempre la descripción extraída del PDF.
- El parser registra versión y estado (`ready`, `partial` o `failed`).
- Ninguna credencial ni PDF se registra en Git, logs de aplicación o telemetría externa.

## Estados de pantalla y datos parciales

| Pantalla | Carga | Vacío | Error | Parcial |
|---|---|---|---|---|
| Tickets | Skeleton de filas y controles deshabilitados | “Aún no hay tickets sincronizados” + acción de sincronizar | Código accionable y reintento | Badge `Parcial` en la fila |
| Ticket | Skeleton de cabecera y líneas | No aplica si existe el ticket | 404 o error de carga con volver | Banner con líneas no interpretadas |
| Productos | Input usable y lista skeleton | “No se encontraron productos” | Error de búsqueda con reintento | Producto visible sólo con observaciones válidas |
| Sincronización | Estado de ejecución y última actividad | “Nunca se ha sincronizado” | Error con causa y acción | Conteo de mensajes/líneas parciales |

## Reglas exactas de precio comparable

1. `lineAmountCents` es el importe total de la línea.
2. Para una línea por unidades:
   - `quantity` es el número de unidades, conservando decimales si el documento los informa.
   - si el ticket informa precio unitario explícito, se usa ese valor;
   - si no, `comparablePriceCents = round_half_up(lineAmount / quantity)`;
   - `comparableBasis = unit`.
3. Para una línea a peso:
   - `weightGrams` es el peso cobrado;
   - `pricePerKgCents` explícito, si existe, es la fuente preferente;
   - si no, `comparablePriceCents = round_half_up(lineAmount * 1000 / weightGrams)`;
   - `comparableBasis = kg`.
4. Si faltan cantidad, peso o importe, la línea queda `partial` y no entra en la serie histórica.
5. No se convierten unidades a kg ni se mezclan bases dentro de una misma gráfica.

El redondeo ocurre una sola vez en el límite de dominio y usa `Decimal` con `ROUND_HALF_UP`; la API expone enteros de céntimos y nunca `float`.

## Normalización conservadora

Se guardan `rawDescription` y `normalizedDescription`. La normalización sólo elimina espacios redundantes, normaliza mayúsculas/minúsculas, Unicode y puntuación no semántica. No elimina tamaños, formatos, marcas, variedades ni cantidades. Un alias sólo se vincula automáticamente cuando la clave normalizada y la base (`unit`/`kg`) son inequívocas; los conflictos se dejan sin vincular para revisión. No se fusionan productos automáticamente por similitud difusa.

## Requisitos no funcionales y seguridad

- Backend Python 3.13, FastAPI, SQLAlchemy 2, Alembic y Pydantic 2.
- SQLite en WAL inicialmente; repositorios y tipos de dominio independientes del motor para migrar a PostgreSQL.
- Frontend React + TypeScript estricto + Vite + Tailwind + Zustand sólo para UI + TanStack Query para datos remotos + React Router + Recharts.
- El backend es single-user y local-first. El acceso móvil se ofrece sólo por Tailscale, con firewall y token de aplicación local; no se publica ningún puerto en Internet.
- OAuth Gmail usa `gmail.readonly`; los tokens se guardan fuera del repositorio, con permisos restrictivos y, cuando sea posible, cifrado del almacén de credenciales del sistema operativo.
- CORS sólo permite los orígenes configurados. Los logs excluyen tokens, cuerpos de correo, PDF y datos innecesarios.
- El PDF se trata como entrada no confiable: límites de tamaño, timeout de parsing, validación de MIME y almacenamiento fuera de la raíz pública.

## Matriz de trazabilidad y pruebas

| Requisito | Endpoint principal | Tablas | Test mínimo |
|---|---|---|---|
| RF-01 | `GET /api/v1/tickets` | `tickets`, `ticket_items` | `test_tickets_page_is_stable_and_max_50` |
| RF-02 | `GET /api/v1/tickets/{ticketId}` | `tickets`, `ticket_items`, `products` | `test_ticket_detail_exposes_unit_and_kg_without_mixing` |
| RF-03 | `GET /api/v1/products/search`, `GET /api/v1/products/{id}`, `GET /api/v1/products/{id}/tickets` | `products`, `product_aliases`, `ticket_items`, `tickets` | `test_product_history_and_accessible_table_share_basis` |
| RF-04 | `POST /api/v1/sync-runs`, `GET /api/v1/sync-runs/{id}`, `GET /api/v1/sync/status` | `gmail_messages`, `sync_runs`, `tickets` | `test_sync_is_idempotent_by_gmail_message_and_sha256` |
| RF-05 | Interno + `GET /api/v1/tickets/{id}` | `gmail_messages`, `tickets`, `ticket_items` | `test_original_pdf_hash_and_parser_status_are_traceable` |
| Seguridad | Todos los endpoints | `sync_runs` sólo para auditoría técnica | `test_cors_auth_and_logs_do_not_expose_secrets` |
