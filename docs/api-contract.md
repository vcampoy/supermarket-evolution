# Contrato REST

Base URL: `/api/v1`. JSON en UTF-8. Los importes son enteros de céntimos y las fechas son ISO 8601. La API no devuelve `float`.

## Convenciones comunes

### Autorización

Las peticiones remotas por Tailscale requieren `Authorization: Bearer <LOCAL_APP_TOKEN>`. El token de aplicación es distinto del OAuth de Gmail y nunca se devuelve por API. En desarrollo local, el modo loopback puede omitirlo según configuración explícita.

### Paginación

Los listados usan `page` base 1. `pageSize=50` es obligatorio para tickets y productos asociados a un ticket; cualquier otro tamaño para esos recursos devuelve `422`. Las respuestas incluyen:

```json
{
  "items": [],
  "page": 1,
  "pageSize": 50,
  "totalItems": 0,
  "totalPages": 0
}
```

### Error

```json
{
  "error": {
    "code": "TICKET_NOT_FOUND",
    "message": "Ticket not found",
    "details": {},
    "requestId": "req_01J..."
  }
}
```

`message` es seguro para mostrar; `details` no contiene tokens, cuerpos de correo ni rutas privadas.

## Salud y sincronización

### `GET /health`

No requiere autenticación en loopback. Devuelve estado técnico mínimo.

```json
{ "status": "ok", "database": "ok", "version": "0.1.0" }
```

### `GET /sync/status`

Devuelve la ejecución actual, última ejecución y si el host puede sincronizar.

```json
{
  "running": false,
  "lastRun": {
    "id": "2d6b8c7e-2d64-4e7b-b8cc-e7f9a8c67a10",
    "mode": "incremental",
    "status": "succeeded",
    "startedAt": "2026-09-18T01:00:00Z",
    "finishedAt": "2026-09-18T01:02:14Z",
    "importedTickets": 4,
    "partialTickets": 0,
    "errorCount": 0
  },
  "nextScheduledAt": "2026-09-19T03:00:00+02:00",
  "hostOnline": true
}
```

### `POST /sync-runs`

Inicia un backfill, incremental o ejecución manual. `manual` es el valor usado por el botón.

Request:

```json
{ "mode": "manual" }
```

Response `202 Accepted`:

```json
{ "id": "2d6b8c7e-2d64-4e7b-b8cc-e7f9a8c67a10", "mode": "manual", "status": "queued" }
```

Errores: `409 SYNC_ALREADY_RUNNING`, `503 GMAIL_UNAVAILABLE`, `422 INVALID_SYNC_MODE`.

### `GET /sync-runs/{syncRunId}`

Devuelve progreso y errores agregados.

```json
{
  "id": "2d6b8c7e-2d64-4e7b-b8cc-e7f9a8c67a10",
  "mode": "manual",
  "status": "partial",
  "matchedMessages": 12,
  "importedTickets": 10,
  "skippedDuplicates": 1,
  "partialTickets": 1,
  "errorCount": 1,
  "errors": [{ "code": "PDF_PARSE_PARTIAL", "count": 1 }]
}
```

Errores: `404 SYNC_RUN_NOT_FOUND`.

## Tickets

### `GET /tickets?page=1&pageSize=50`

Orden fijo: `purchasedAt DESC, id DESC`.

```json
{
  "items": [
    {
      "id": "a1cc8c26-4fd5-4ac0-8ab0-9f322f25f5b1",
      "purchasedAt": "2026-09-17T18:42:00+02:00",
      "timezone": "Europe/Madrid",
      "lineCount": 23,
      "totalCents": 1290,
      "parseStatus": "ready"
    }
  ],
  "page": 1,
  "pageSize": 50,
  "totalItems": 1,
  "totalPages": 1
}
```

Errores: `422 INVALID_PAGE`, `422 INVALID_PAGE_SIZE`.

### `GET /tickets/{ticketId}`

```json
{
  "id": "a1cc8c26-4fd5-4ac0-8ab0-9f322f25f5b1",
  "ticketNumber": "123456",
  "purchasedAt": "2026-09-17T18:42:00+02:00",
  "timezone": "Europe/Madrid",
  "totalCents": 1290,
  "parseStatus": "partial",
  "originalPdf": { "available": true, "sha256": "abc..." },
  "items": [
    {
      "id": "8ef7af5b-c07e-4f2f-8f8e-2e850d1dc531",
      "lineIndex": 1,
      "rawDescription": "Tomate pera",
      "product": { "id": "4e21...", "name": "Tomate pera", "basis": "kg" },
      "quantity": null,
      "quantityUnit": "kg",
      "weightGrams": 740,
      "comparablePriceCents": 219,
      "comparableBasis": "kg",
      "lineAmountCents": 162,
      "parseStatus": "ready"
    }
  ]
}
```

El backend ya calcula `comparablePriceCents`; React no lo recalcula. Errores: `404 TICKET_NOT_FOUND`, `422 INVALID_UUID`.

## Productos

### `GET /products/search?q=tom&limit=10`

La búsqueda sólo devuelve productos canónicos activos y su base.

```json
{ "items": [
  { "id": "4e21...", "name": "Tomate pera", "basis": "kg", "match": "Tomate pera" }
] }
```

Errores: `422 QUERY_TOO_SHORT` para una búsqueda no vacía de menos de 2 caracteres, `422 INVALID_LIMIT`.

### `GET /products/{productId}`

```json
{
  "id": "4e21...",
  "name": "Tomate pera",
  "basis": "kg",
  "summary": {
    "firstPriceCents": 199,
    "lastPriceCents": 219,
    "changeCents": 20,
    "changePercent": 10.05,
    "observationCount": 4
  },
  "priceHistory": [
    { "ticketId": "a1cc...", "purchasedAt": "2026-08-01T10:00:00+02:00", "priceCents": 199, "basis": "kg" },
    { "ticketId": "a1cc...", "purchasedAt": "2026-09-17T18:42:00+02:00", "priceCents": 219, "basis": "kg" }
  ]
}
```

`priceHistory` sólo contiene líneas `ready` de la base del producto y se devuelve ordenado ascendente para la gráfica. `changePercent` es `null` si el precio inicial es cero o no hay dos observaciones. Errores: `404 PRODUCT_NOT_FOUND`, `422 INVALID_UUID`.

### `GET /products/{productId}/tickets?page=1&pageSize=50`

Devuelve los tickets y líneas que originan las observaciones del producto:

```json
{
  "items": [
    {
      "ticketId": "a1cc...",
      "purchasedAt": "2026-09-17T18:42:00+02:00",
      "lineAmountCents": 162,
      "comparablePriceCents": 219,
      "basis": "kg"
    }
  ],
  "page": 1,
  "pageSize": 50,
  "totalItems": 1,
  "totalPages": 1
}
```

## Códigos de error mínimos

| HTTP | Código | Situación |
|---:|---|---|
| 400 | `MALFORMED_JSON` | Cuerpo no interpretable |
| 401 | `AUTH_REQUIRED` / `AUTH_INVALID` | Token local ausente o inválido |
| 404 | `TICKET_NOT_FOUND`, `PRODUCT_NOT_FOUND`, `SYNC_RUN_NOT_FOUND` | Recurso inexistente |
| 409 | `SYNC_ALREADY_RUNNING`, `SOURCE_INTEGRITY_CONFLICT` | Conflicto de estado o PDF cambiado |
| 422 | `INVALID_PAGE`, `INVALID_PAGE_SIZE`, `INVALID_UUID`, `INVALID_SYNC_MODE` | Entrada válida como JSON pero inválida para el contrato |
| 429 | `RATE_LIMITED` | Protección de búsqueda o sincronización |
| 503 | `GMAIL_UNAVAILABLE`, `DATABASE_UNAVAILABLE` | Dependencia local o externa no disponible |
