# Scripts operativos

La operación de Gmail vive en el módulo CLI del backend:

```text
cd src/backend
python -m app.cli gmail-auth
python -m app.cli sync --all
python -m app.cli sync --since-last
python -m app.cli parse-file C:\ruta\ticket.pdf
python -m app.cli reparse --failed
```

La guía de credenciales OAuth está en [`docs/gmail-setup.md`](../../docs/gmail-setup.md).
Los secretos y los PDF deben permanecer fuera de Git.
