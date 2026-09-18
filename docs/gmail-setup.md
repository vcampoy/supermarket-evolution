# Configurar Gmail en local

La ingesta usa la API oficial de Gmail con el alcance de sólo lectura
`https://www.googleapis.com/auth/gmail.readonly`. No se guardan contraseñas ni
secretos en el repositorio.

## Credenciales OAuth

1. En [Google Cloud Console](https://console.cloud.google.com/) crea o selecciona un proyecto.
2. Habilita **Gmail API**.
3. Configura la pantalla de consentimiento OAuth como aplicación externa (o interna si la cuenta pertenece a una organización compatible) y añade la cuenta de uso como usuario de prueba cuando corresponda.
4. Crea credenciales **OAuth client ID → Desktop app**.
5. Descarga el JSON y guárdalo fuera de Git, por ejemplo en `C:\Source\supermarket-evolution\secrets\gmail-client-secret.json`.
6. Desde `src/backend`, ejecuta `.\.venv\Scripts\python.exe -m app.cli gmail-auth`. Se abrirá el navegador para el consentimiento manual y se guardará el refresh token en `SUPERMARKET_GMAIL_TOKEN_PATH` (por defecto `../../secrets/gmail-token.json`).
7. Comprueba que la cuenta autorizada coincide con `SUPERMARKET_GMAIL_ACCOUNT`.

## Variables configurables

```text
SUPERMARKET_GMAIL_ACCOUNT=dantecampoy@gmail.com
SUPERMARKET_GMAIL_SENDER=ticket_digital@mail.mercadona.com
SUPERMARKET_GMAIL_QUERY=from:(ticket_digital@mail.mercadona.com) has:attachment filename:pdf
SUPERMARKET_GMAIL_CLIENT_SECRETS_PATH=../../secrets/gmail-client-secret.json
SUPERMARKET_GMAIL_TOKEN_PATH=../../secrets/gmail-token.json
SUPERMARKET_TICKETS_DIRECTORY=../../tickets
```

La consulta de backfill es `.\.venv\Scripts\python.exe -m app.cli sync --all`;
las siguientes ejecuciones usan
`.\.venv\Scripts\python.exe -m app.cli sync --since-last`. Los mensajes no se
marcan, mueven ni borran. La aplicación sólo registra identificadores,
metadatos, hashes y estados seguros; nunca imprime tokens ni el texto completo
de un ticket.
