# ADR 0001: arquitectura local-first con acceso por Tailscale

- **Estado:** Aceptada
- **Fecha:** 2026-09-18
- **Decisores:** Proyecto Mercadona Evolution

## Contexto

La aplicación es de un solo usuario y maneja PDF de tickets, historial de compras y credenciales de Gmail. Debe consultar los datos desde escritorio y móvil, pero no necesita ser pública ni multiusuario. La sincronización depende de Gmail y debe ejecutarse cada noche a las 03:00, además de recuperarse cuando el PC vuelva a arrancar.

## Decisión

El PC del usuario será la autoridad de datos y ejecutará backend, frontend servido y scheduler. SQLite en WAL almacenará el índice estructurado; los PDF originales permanecerán en `tickets/`. El acceso móvil se habilitará únicamente a través de la red privada Tailscale, con ACL de tailnet, firewall de Windows y token de aplicación para la API. No habrá despliegue público ni port-forwarding.

El diseño separa dominio, aplicación, infraestructura y API. Los puertos de repositorio y servicios de Gmail/PDF permiten migrar el almacenamiento sin trasladar reglas de negocio.

## Motivos

1. **Privacidad:** los PDF y el historial no abandonan el equipo salvo la consulta de Gmail y el tráfico cifrado de Tailscale.
2. **Simplicidad operativa:** no hay servidor público, base de datos gestionada ni sistema multiusuario que mantener.
3. **Coste:** evita infraestructura recurrente para una aplicación personal.
4. **Disponibilidad controlada:** escritorio y móvil pueden acceder mientras el PC está encendido; el scheduler no depende de un servicio externo.
5. **Migrabilidad:** SQLAlchemy, Alembic, repositorios y tipos portables dejan PostgreSQL como evolución posible.

## Consecuencias

### Positivas

- Los originales se preservan junto a su hash y trazabilidad.
- El usuario controla backups, retención y credenciales.
- Tailscale evita exponer puertos a Internet y proporciona cifrado entre dispositivos.
- SQLite WAL ofrece lecturas concurrentes razonables para la carga de un solo usuario.

### Negativas y límites

- El PC debe estar encendido para sincronizar a las 03:00 y para consultar desde móvil.
- Un fallo o disco perdido en el PC requiere restaurar un backup; Tailscale no es backup.
- La disponibilidad móvil depende de la red del PC y de Tailscale.
- SQLite no es el destino ideal para muchos escritores o multiusuario; no se debe forzar ese escenario.
- Los tokens de Gmail siguen siendo material sensible aunque no estén en la nube del proyecto.

## Controles operativos obligatorios

- Backup periódico cifrado de la base y de `tickets/`; probar restauración.
- No guardar `.env`, tokens, PDFs ni dumps en Git.
- Mantener Tailscale ACL y Windows Firewall restringidos a dispositivos propios.
- Bind local por defecto; habilitar escucha por Tailscale sólo de forma explícita.
- Usar token de aplicación en accesos remotos y CORS allowlist; no cookies de sesión para el cliente móvil.
- Mostrar en la UI la última sincronización y advertir cuando el host no está disponible.

## Alternativas consideradas

| Alternativa | Motivo para no elegirla ahora |
|---|---|
| Servicio público con PostgreSQL gestionado | Aumenta superficie de exposición, coste y complejidad para un solo usuario. |
| Acceso directo por IP/port-forwarding | Expone una aplicación con datos personales a Internet y delega seguridad en el router. |
| Sólo acceso local | No satisface la consulta desde móvil; Tailscale añade alcance privado sin hacer público el servicio. |
| Google Drive/Dropbox como almacén principal | Cambia la autoridad de datos y complica la trazabilidad e integridad del PDF original. |

## Camino de migración a nube

Si el alcance cambia a multiusuario o disponibilidad 24/7:

1. Mantener el dominio y casos de uso sin cambios.
2. Crear un adaptador PostgreSQL y ejecutar migraciones Alembic sobre una copia validada.
3. Migrar PDF a almacenamiento de objetos privado con SHA-256 como clave o metadato.
4. Sustituir scheduler local por un worker/cola con lock distribuido.
5. Añadir identidad multiusuario, autorización por recurso, gestión de secretos y observabilidad explícita.
6. Ejecutar comparación de conteos, hashes y precios antes de cambiar la lectura a la nube.

La migración no se considera automática: debe conservar los mismos invariantes de dinero, bases comparables, deduplicación por Gmail y estado parcial.
